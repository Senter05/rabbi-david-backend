"""Covenant of Provision: private download page, signed file links, emails and Stripe fallback (no network)."""
import unittest, tempfile, threading, urllib.request, urllib.error, urllib.parse, json, io, time, email
from email import policy
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server

PORT = 8108
REAL_URLOPEN = urllib.request.urlopen
CS7 = 'cs_test_seven0000000000000001'
CSC = 'cs_test_complete000000000001'


class FakeStripe:
    """Answers only api.stripe.com; anything else goes to the real local server."""
    def __init__(self, sessions):
        self.sessions = sessions; self.gets = []; self.posts = []
    def __call__(self, req, *a, **k):
        url = req.full_url if hasattr(req, 'full_url') else req
        if 'api.stripe.com' not in url: return REAL_URLOPEN(req, *a, **k)
        if req.data:
            self.posts.append(dict(urllib.parse.parse_qsl(req.data.decode())))
            return io.BytesIO(json.dumps({'id': 'cs_test_newcheckout0001', 'url': 'https://checkout.stripe.com/c/pay/x'}).encode())
        sid = url.rsplit('/', 1)[1]; self.gets.append(sid)
        if sid not in self.sessions: raise urllib.error.HTTPError(url, 404, 'nf', {}, io.BytesIO(b'{}'))
        return io.BytesIO(json.dumps(self.sessions[sid]).encode())


def paid(sid, book, amount, mail='late@example.com', status='paid'):
    return {'id': sid, 'payment_status': status, 'amount_total': amount, 'currency': 'usd',
            'customer_details': {'email': mail, 'name': 'Miriam Cohen'}, 'metadata': {'book_id': book}}


class CovenantDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); server.AI_ENABLED = False; server.VOICE_ENABLED = False
        server.EMAIL_RESOLVER = lambda domain: True
        server.init({'max_requests_per_minute': 5000, 'max_jobs_per_day': 1000, 'stripe_secret_key': 'sk_test_dummy',
                     'public_origin': 'https://rabbidavid.org'}, cls.tmp.name, PORT)
        cls.http = ThreadingHTTPServer(('127.0.0.1', PORT), server.Handler)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()
        server.deliver_ebook('ord_' + CS7, 'seven@example.com', 'Ruth', 'covenant_7day', session_id=CS7, amount=2200)
        server.deliver_ebook('ord_' + CSC, 'full@example.com', 'Ruth', 'covenant_complete', session_id=CSC, amount=9200)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.tmp.cleanup()

    def get(self, path, headers=None):
        r = urllib.request.Request(f'http://127.0.0.1:{PORT}' + path, headers={'X-Requested-With': 'RabbiDavid', **(headers or {})})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k): return None
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(r, timeout=15) as resp: return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read()

    def access(self, sid):
        code, h, body = self.get('/api/covenant/access?session_id=' + urllib.parse.quote(sid))
        return code, json.loads(body)

    # ---- download page data ----
    def test_7day_gets_only_its_pdf(self):
        code, d = self.access(CS7)
        self.assertEqual(code, 200); self.assertTrue(d['verified'])
        self.assertEqual([p['file'] for p in d['pdfs']], ['The-7-Day-Command-Over-Money.pdf'])
        self.assertEqual(d['audios'], []); self.assertIsNone(d['zip_url']); self.assertEqual(d['bonus'], [])

    def test_complete_gets_books_12_audios_zip_and_6_bonus(self):
        code, d = self.access(CSC)
        self.assertEqual(len(d['pdfs']), 2); self.assertEqual(len(d['audios']), 12); self.assertEqual(len(d['bonus']), 6)
        self.assertTrue(d['zip_url'].startswith('/api/covenant/file?'))
        self.assertEqual(d['audios'][0]['title'], 'Modeh Ani — The Morning Decree')
        self.assertEqual(d['audios'][11]['title'], 'The Night Shema and Peace')

    def test_unknown_or_malformed_session_is_not_verified(self):
        with patch('urllib.request.urlopen', FakeStripe({})):
            code, d = self.access('cs_test_doesnotexist00000001')
        self.assertEqual(code, 200); self.assertFalse(d['verified'])
        code, d = self.access('../../etc/passwd'); self.assertEqual(code, 400); self.assertFalse(d['verified'])

    # ---- signed files ----
    def test_signed_pdf_is_served_privately(self):
        d = self.access(CSC)[1]
        code, h, body = self.get(d['pdfs'][1]['download_url'])
        self.assertEqual(code, 200); self.assertTrue(body.startswith(b'%PDF'))
        self.assertEqual(h['Content-Type'], 'application/pdf'); self.assertEqual(h['Cache-Control'], 'no-store')
        self.assertIn('attachment; filename="The-Complete-Covenant-of-Provision.pdf"', h['Content-Disposition'])

    def test_audio_supports_range_for_html5_player(self):
        d = self.access(CSC)[1]
        code, h, body = self.get(d['audios'][2]['url'], {'Range': 'bytes=0-1023'})
        self.assertEqual(code, 206); self.assertEqual(len(body), 1024); self.assertEqual(h['Content-Type'], 'audio/mpeg')
        self.assertTrue(h['Content-Disposition'].startswith('inline'))

    def test_zip_download(self):
        d = self.access(CSC)[1]
        code, h, body = self.get(d['zip_url'], {'Range': 'bytes=0-3'})
        self.assertEqual(code, 206); self.assertEqual(body, b'PK\x03\x04')
        self.assertIn('Covenant-of-Provision-Audios.zip', h['Content-Disposition'])

    def test_tampered_expired_and_unentitled_links_are_refused(self):
        d = self.access(CSC)[1]
        url = d['audios'][0]['url']
        self.assertEqual(self.get(url.replace('audio%3A01', 'audio%3A02'))[0], 403)  # signature covers file id
        self.assertEqual(self.get(url.replace('s=' + CSC, 's=' + CS7))[0], 403)       # and session id
        old = server.covenant_link(CSC, 'audio:01', now=time.time() - server.COVENANT_LINK_TTL - 10)
        self.assertEqual(self.get(old)[0], 403)
        forged = server.covenant_link(CS7, 'audio:01')                                  # validly signed, not bought
        self.assertEqual(self.get(forged)[0], 403)
        self.assertEqual(self.get(server.covenant_link(CS7, 'pdf:The-Complete-Covenant-of-Provision.pdf'))[0], 403)
        self.assertEqual(self.get('/api/covenant/file?s=' + CSC + '&f=zip&e=9999999999&k=00')[0], 403)

    def test_missing_local_file_redirects_to_supabase_signed_url(self):
        d = self.access(CSC)[1]
        with patch.object(server, 'covenant_file_table', lambda: {'audio:01': ([server.ROOT / 'nope.mp3'], 'covenant/01-covenant-audio.mp3', '01 x.mp3', 'audio/mpeg')}), \
             patch.object(server, 'supabase_signed_url', lambda name, exp=3600, dn=None: 'https://example.supabase.co/storage/v1/object/sign/user-assets/' + name + '?token=t'):
            code, h, body = self.get(d['audios'][0]['url'])
        self.assertEqual(code, 302); self.assertIn('/object/sign/user-assets/covenant/01-covenant-audio.mp3', h['Location'])

    def test_new_core_pdfs_are_not_in_public(self):
        for f in ('The-7-Day-Command-Over-Money.pdf', 'The-Complete-Covenant-of-Provision.pdf'):
            self.assertFalse((server.ROOT / 'public' / 'pdf' / f).exists())
            self.assertEqual(self.get('/pdf/' + f)[0], 404)
        self.assertEqual(self.get('/private_assets/covenant/01-covenant-audio.mp3')[0], 404)

    # ---- emails ----
    def capture(self, fn):
        sent = []
        with patch.object(server, 'mail_configured', lambda: True), \
             patch.object(server.mail_delivery, 'send', lambda cfg, msg, mid: sent.append((msg, mid)) or 'prov_' + mid):
            result = fn()
        return result, sent

    def test_purchase_email_has_private_link_and_pdfs(self):
        sid = 'cs_test_mailcheck00000000001'
        res, sent = self.capture(lambda: server.deliver_ebook('ord_' + sid, 'm@example.com', 'Miriam Cohen', 'covenant_complete', session_id=sid, amount=9200))
        self.assertEqual(res['status'], 'sent'); self.assertEqual(len(sent), 1)
        msg = sent[0][0]
        text = msg.get_body(preferencelist=('plain',)).get_content()
        self.assertIn('Shalom Miriam', text)
        self.assertIn('https://rabbidavid.org/download/covenant.html?session_id=' + sid, text)
        self.assertIn('12 audios', text)
        html = msg.get_body(preferencelist=('html',)).get_content()
        self.assertIn('Open my download page', html)
        names = [p.get_filename() for p in msg.iter_attachments()]
        self.assertEqual(names, ['The-7-Day-Command-Over-Money.pdf', 'The-Complete-Covenant-of-Provision.pdf'])
        size = sum(len(p.get_payload(decode=True)) for p in msg.iter_attachments())
        self.assertLess(size * 4 / 3, 40_000_000)  # Resend limit after base64
        # Webhook arriving after the Stripe fallback must not email twice.
        res2, sent2 = self.capture(lambda: server.deliver_ebook('ord_' + sid, 'm@example.com', 'Miriam', 'covenant_complete', session_id=sid, amount=9200))
        self.assertEqual(sent2, []); self.assertTrue(res2.get('duplicate'))

    def test_7day_email(self):
        sid = 'cs_test_mailseven0000000001'
        res, sent = self.capture(lambda: server.deliver_ebook('ord_' + sid, 's@example.com', 'Valued Reader', 'covenant_7day', session_id=sid, amount=2200))
        msg = sent[0][0]; text = msg.get_body(preferencelist=('plain',)).get_content()
        self.assertIn('Shalom Friend', text); self.assertNotIn('12 audios', text)
        self.assertEqual([p.get_filename() for p in msg.iter_attachments()], ['The-7-Day-Command-Over-Money.pdf'])

    def test_local_mode_writes_outbox_and_never_sends(self):
        sid = 'cs_test_outbox000000000001'
        with patch.object(server.mail_delivery, 'send', side_effect=AssertionError('no real mail')):
            res = server.deliver_ebook('ord_' + sid, 'o@example.com', 'Ruth', 'covenant_7day', session_id=sid, amount=2200)
        self.assertEqual(res['status'], 'local_preview')
        eml = (server.DATA / 'outbox' / ('ord_' + sid + '.eml')).read_bytes()
        self.assertIn(b'/download/covenant.html?session_id=' + sid.encode(), email.message_from_bytes(eml, policy=policy.default).get_body(preferencelist=('plain',)).get_content().encode())

    def test_lead_sends_day1_gift_once(self):
        def post():
            r = urllib.request.Request(f'http://127.0.0.1:{PORT}/api/lead', data=json.dumps({'email': 'gift@example.com', 'name': 'Esther'}).encode(),
                                       headers={'X-Requested-With': 'RabbiDavid', 'Content-Type': 'application/json'})
            with REAL_URLOPEN(r, timeout=15) as resp: return json.loads(resp.read())
        (d1, d2), sent = self.capture(lambda: (post(), post()))
        self.assertEqual(len(sent), 1); self.assertEqual(d1['gift_status'], 'sent'); self.assertEqual(d2['gift_status'], 'sent')
        self.assertEqual(d1['gift_url'], '/pdf/Day-1-The-Psalm-That-Opens-the-Door.pdf')
        msg = sent[0][0]
        self.assertEqual(str(msg['To']), 'gift@example.com'); self.assertIn('Day 1', str(msg['Subject']))
        self.assertIn('Shalom Esther', msg.get_body(preferencelist=('plain',)).get_content())
        self.assertIn('unsubscribe', msg.get_body(preferencelist=('plain',)).get_content())
        self.assertEqual([p.get_filename() for p in msg.iter_attachments()], ['Day-1-The-Psalm-That-Opens-the-Door.pdf'])
        with server.connection() as con:
            self.assertEqual(con.execute("SELECT gift_status FROM leads WHERE email='gift@example.com'").fetchone()[0], 'sent')

    def test_gift_failure_is_retried_on_next_request(self):
        with patch.object(server, 'mail_configured', lambda: True), \
             patch.object(server.mail_delivery, 'send', side_effect=server.mail_delivery.MailDeliveryError('resend_http_429_rate_limit')):
            self.assertEqual(server.record_lead('retry@example.com', 'A', 'covenant'), 'failed')
        _, sent = self.capture(lambda: server.record_lead('retry@example.com', 'A', 'covenant'))
        self.assertEqual(len(sent), 1)

    # ---- upsell / Stripe fallback when the webhook is late ----
    def test_thanks_page_verifies_through_stripe_before_webhook(self):
        sid = 'cs_test_latewebhook0000001'
        fake = FakeStripe({sid: paid(sid, 'covenant_7day', 2200)})
        with patch('urllib.request.urlopen', fake), patch.object(server.mail_delivery, 'send', side_effect=AssertionError):
            code, h, body = self.get('/api/download-verify?session_id=' + sid)
            d = json.loads(body)
            self.assertTrue(d['verified']); self.assertEqual(d['book_id'], 'covenant_7day'); self.assertEqual(d['email'], 'late@example.com')
            # Upsell now works right away, without the webhook
            r = urllib.request.Request(f'http://127.0.0.1:{PORT}/api/create-ebook-checkout',
                                       data=json.dumps({'book_id': 'covenant_upgrade', 'prior_session_id': sid}).encode(),
                                       headers={'X-Requested-With': 'RabbiDavid', 'Content-Type': 'application/json'})
            with REAL_URLOPEN(r, timeout=15) as resp: self.assertEqual(resp.status, 200)
            # Webhook later: no second order/email
            server.deliver_ebook('ord_' + sid, 'late@example.com', 'Miriam', 'covenant_7day', session_id=sid, amount=2200)
        self.assertEqual(fake.gets, [sid])
        p = fake.posts[0]
        self.assertEqual(p['line_items[0][price_data][unit_amount]'], '7000'); self.assertEqual(p['customer_email'], 'late@example.com')
        with server.connection() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM orders WHERE session_id=?', (sid,)).fetchone()[0], 1)

    def test_upgrade_session_unlocks_everything(self):
        sid = 'cs_test_upgradepaid0000001'
        with patch('urllib.request.urlopen', FakeStripe({sid: paid(sid, 'covenant_upgrade', 7000)})):
            code, d = self.access(sid)
        self.assertTrue(d['verified']); self.assertEqual(len(d['audios']), 12); self.assertEqual(len(d['pdfs']), 2); self.assertEqual(len(d['bonus']), 6)

    def test_unpaid_or_foreign_stripe_sessions_unlock_nothing(self):
        a, b = 'cs_test_unpaid000000000001', 'cs_test_otherbook000000001'
        fake = FakeStripe({a: paid(a, 'covenant_complete', 9200, status='unpaid'), b: paid(b, 'morning', 2200)})
        with patch('urllib.request.urlopen', fake):
            self.assertFalse(self.access(a)[1]['verified']); self.assertFalse(self.access(b)[1]['verified'])
        with server.connection() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM orders WHERE session_id IN (?,?)', (a, b)).fetchone()[0], 0)

    def test_no_stripe_key_means_no_stripe_call(self):
        old = server.CONFIG.get('stripe_secret_key'); server.CONFIG['stripe_secret_key'] = ''
        try:
            with patch('urllib.request.urlopen', side_effect=AssertionError('no network')):
                self.assertIsNone(server.covenant_stripe_sync('cs_test_nokey000000000001'))
        finally:
            server.CONFIG['stripe_secret_key'] = old


if __name__ == '__main__':
    unittest.main()

import unittest,tempfile,os,time,threading,urllib.request,json,http.cookiejar
from unittest.mock import patch
import server,operations,test_app

class SecurityTests(unittest.TestCase):
    setUpClass=classmethod(test_app.JourneyTests.setUpClass.__func__)
    tearDownClass=classmethod(test_app.JourneyTests.tearDownClass.__func__)
    setUp=test_app.JourneyTests.setUp
    req=test_app.JourneyTests.req
    def test_edit_after_failure_returns_to_draft_and_preserves_answers(self):
        sid=server.new_session();answers=test_app.example()
        server.update(sid,lambda d:d.update(started=True,email='alex@example.com',answers=answers,status='error',error='Generation failed',generation_progress={'completed':1,'total':5}))
        code,state=self.req('/api/save',{'answers':answers,'step':0},headers={'Cookie':'rd_session='+sid})
        self.assertEqual(code,200);self.assertEqual(state['status'],'draft')
        self.assertEqual(state['answers'],answers);self.assertEqual(state['step'],0)
        self.assertIsNone(state['error']);self.assertIsNone(state['generation_progress'])
    def test_production_rejects_foreign_origins_and_wildcard_hosts(self):
        with patch.dict(os.environ,{'PRODUCTION':'1','RENDER':'true'}):
            for origin in ['https://untrusted.example','https://other-app.onrender.com','null']:
                self.assertEqual(self.req('/api/state',headers={'Origin':origin})[0],403)
                self.assertEqual(self.req('/api/enroll',{'name':'Alex','email':'alex@example.com','password':'FixturePassword123'},headers={'Origin':origin})[0],403)
            self.assertEqual(self.req('/api/state',headers={'Host':'attacker.example'})[0],403)
    def test_same_origin_and_international_email(self):
        status,data=self.req('/api/enroll',{'name':'Alex','email':'alex@bücher.de','password':'FixturePassword123'},headers={'Origin':'http://127.0.0.1:8101'})
        self.assertEqual(status,200);self.assertEqual(data['email'],'alex@xn--bcher-kva.de')
    def test_recovery_key_cross_browser_rotates_and_deletion_revokes(self):
        self.req('/api/enroll',{'name':'Alex','email':'alex@example.com','password':'FixturePassword123'})
        _,first=self.req('/api/recovery-key',{})
        _,second=self.req('/api/recovery-key',{})
        other=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.assertEqual(self.req('/api/recover-key',{'key':first['key']},client=other)[0],400)
        self.assertEqual(self.req('/api/recover-key',{'key':second['key']},client=other)[0],200)
        self.assertEqual(self.req('/api/state',client=other)[1]['email'],'alex@example.com')
        self.assertEqual(self.req('/api/delete',{'confirmation':'DELETE'},client=other)[0],200)
        self.assertEqual(self.req('/api/recover-key',{'key':second['key']})[0],400)
    def test_static_cache_ranges_and_no_session_cookie(self):
        request=urllib.request.Request('http://127.0.0.1:8101/images/ebook-prayer-cover.webp',headers={'Range':'bytes=0-1023'})
        with self.client.open(request) as result:
            self.assertEqual(result.status,206);self.assertEqual(len(result.read()),1024)
            self.assertIsNone(result.headers.get('Set-Cookie'));self.assertIn('public',result.headers['Cache-Control'])
        self.assertEqual(self.req('/images/ebook-prayer-cover.webp',headers={'Range':'bytes=999999999-9999999999'},raw=True)[0],416)
    def test_followup_concurrent_calls_only_generate_once(self):
        self.req('/api/enroll',{'name':'Alex','email':'alex@example.com','password':'FixturePassword123'});self.req('/api/save',{'answers':test_app.example(),'step':12})
        entered=threading.Event();release=threading.Event();results=[]
        def mock(*args):entered.set();release.wait(3);return 'What would help you feel more settled?'
        def call():results.append(self.req('/api/followup',{'consent':True})[0])
        with patch.object(server,'AI_ENABLED',True),patch.object(server,'generate_followup',side_effect=mock) as provider:
            task=threading.Thread(target=call);task.start();self.assertTrue(entered.wait(2))
            self.assertEqual(self.req('/api/followup',{'consent':True})[0],409);release.set();task.join(4)
            self.assertEqual(provider.call_count,1);self.assertEqual(results,[200])
    def test_voice_timeout_does_not_submit_again(self):
        sid=server.new_session();server.update(sid,lambda d:d.update(voice={'status':'processing','task_id':'existing','submitted_at':time.time()-1900}))
        with patch.object(server,'poll_voice') as poll,patch.object(server,'submit_voice') as submit:server.process_voice(sid,'voice')
        poll.assert_not_called();submit.assert_not_called();self.assertEqual(server.get(sid)['voice']['status'],'needs_review')
    def test_failed_voice_poll_backs_off(self):
        sid=server.new_session();server.update(sid,lambda d:d.update(voice={'status':'processing','task_id':'existing','submitted_at':time.time()}))
        with patch.object(server,'poll_voice',side_effect=RuntimeError()) as poll:
            server.process_voice(sid,'voice');server.process_voice(sid,'voice')
        self.assertEqual(poll.call_count,1);self.assertGreater(server.get(sid)['voice']['next_poll_at'],time.time())
    def test_contact_validation_and_receipt(self):
        code,data=self.req('/api/support',{'name':'Alex','email':'alex@example.com','category':'privacy','message':'Please explain how I can export my reading.'})
        self.assertEqual(code,200);self.assertEqual(len(data['reference']),8)
    def test_quotas_persist_and_queue_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=tmp+'/limits.sqlite';operations.reserve(db,'text',1)
            with self.assertRaises(operations.CapacityError):operations.reserve(db,'text',1)
        pool=operations.BoundedExecutor(workers=1,capacity=1);release=threading.Event();future=pool.submit(release.wait,3)
        with self.assertRaises(operations.CapacityError):pool.submit(lambda:None)
        release.set();future.result();pool.pool.shutdown()
    def test_provider_budget_stops_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard=operations.ProviderBudget(tmp+'/limits.sqlite',{'max_text_requests_per_day':1})
            guard('https://openrouter.ai/api/v1/chat/completions',b'{}')
            with self.assertRaises(operations.CapacityError):guard('https://openrouter.ai/api/v1/chat/completions',b'{}')
    def test_foreign_preflight_has_no_allow_origin(self):
        request=urllib.request.Request('http://127.0.0.1:8101/api/state',method='OPTIONS',headers={'Origin':'https://untrusted.example'})
        try:self.client.open(request);self.fail('Allowed foreign preflight')
        except urllib.error.HTTPError as result:
            self.assertEqual(result.code,403);self.assertIsNone(result.headers.get('Access-Control-Allow-Origin'))
    def test_smtp_does_not_send_preview_backlog_or_duplicate_sent_mail(self):
        sid=server.new_session();server.update(sid,lambda d:d.update(email='fake@example.com'))
        server.mail(sid,'old','Preview','This must stay local.')
        with patch.dict(server.CONFIG,{'smtp_host':'smtp.example.com','mail_from':'noreply@example.com'}):
            server.mail(sid,'new','Test','New message.')
            with patch('smtplib.SMTP') as smtp:
                server.dispatch_mail_once();server.dispatch_mail_once()
                self.assertEqual(smtp.return_value.__enter__.return_value.send_message.call_count,1)
        with server.connection() as con:rows=dict(con.execute('SELECT kind,delivery_status FROM mail WHERE sid=?',(sid,)))
        self.assertEqual(rows,{'old':'local','new':'sent'})
    def test_budget_failure_restores_retryable_generation_state(self):
        sid=server.new_session();server.update(sid,lambda d:d.update(status='generating',answers=test_app.example()))
        with patch.object(server.POOL,'submit',side_effect=operations.CapacityError('Busy')):
            with self.assertRaises(operations.CapacityError):server.schedule(server.generate_job,sid,0)
        self.assertEqual(server.get(sid)['status'],'error')
if __name__=='__main__':unittest.main()

import unittest,tempfile,threading,urllib.request,urllib.error,urllib.parse,json,io
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server

PORT=8107
REAL_URLOPEN=urllib.request.urlopen

class FakeStripe:
    def __init__(self):self.calls=[]
    def __call__(self,req,*a,**k):
        url=req.full_url if hasattr(req,'full_url') else req
        if 'api.stripe.com' not in url:return REAL_URLOPEN(req,*a,**k)
        self.calls.append(dict(urllib.parse.parse_qsl(req.data.decode())))
        return io.BytesIO(json.dumps({'id':'cs_test_fake','url':'https://checkout.stripe.com/c/pay/cs_test_fake'}).encode())

class CovenantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();server.AI_ENABLED=False;server.VOICE_ENABLED=False
        server.EMAIL_RESOLVER=lambda domain: True
        server.init({'max_requests_per_minute':1000,'max_jobs_per_day':1000,'stripe_secret_key':'sk_test_dummy'},cls.tmp.name,PORT)
        cls.http=ThreadingHTTPServer(('127.0.0.1',PORT),server.Handler)
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
    def req(self,path,data):
        r=urllib.request.Request(f'http://127.0.0.1:{PORT}'+path,data=json.dumps(data).encode(),headers={'X-Requested-With':'RabbiDavid','Content-Type':'application/json'})
        try:
            with REAL_URLOPEN(r,timeout=10) as resp:return resp.status,json.loads(resp.read())
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    def checkout(self,body):
        fake=FakeStripe()
        with patch('urllib.request.urlopen',fake):code,d=self.req('/api/create-ebook-checkout',body)
        return code,d,fake.calls

    def test_two_offers_use_price_data_amounts(self):
        for book,cents in (('covenant_7day','2200'),('covenant_complete','9200')):
            code,d,calls=self.checkout({'book_id':book,'email':'buyer@example.com'})
            self.assertEqual(code,200,d);self.assertTrue(d['checkout_url'].startswith('https://checkout.stripe.com/'))
            p=calls[0]
            self.assertEqual(p['line_items[0][price_data][unit_amount]'],cents)
            self.assertNotIn('line_items[0][price]',p)
            self.assertEqual(p['metadata[book_id]'],book)
            self.assertIn('/covenant-thanks.html?checkout_session_id={CHECKOUT_SESSION_ID}',p['success_url'])
            self.assertTrue(p['cancel_url'].endswith('/covenant.html#offers'))

    def test_upgrade_requires_prior_7day_order(self):
        code,d,calls=self.checkout({'book_id':'covenant_upgrade','prior_session_id':'cs_none'})
        self.assertEqual(code,400);self.assertEqual(calls,[])
        server.deliver_ebook('ord_cs_prior','first@example.com','Ruth','covenant_7day',session_id='cs_prior',amount=2200)
        code,d,calls=self.checkout({'book_id':'covenant_upgrade','prior_session_id':'cs_prior'})
        self.assertEqual(code,200,d)
        p=calls[0];self.assertEqual(p['line_items[0][price_data][unit_amount]'],'7000')
        self.assertEqual(p['metadata[prior_session_id]'],'cs_prior');self.assertEqual(p['customer_email'],'first@example.com')

    def test_covenant_never_falls_back_to_another_book(self):
        res=server.deliver_ebook('ord_cs_x','x@example.com','X','covenant_complete',session_id='cs_x',amount=9200)
        self.assertEqual(res['book_id'],'covenant_complete')
        self.assertTrue(server.covenant_files_ready('covenant_complete'))
        self.assertEqual(res['status'],'local_preview')

    def test_existing_books_unchanged(self):
        code,d,calls=self.checkout({'book_id':'morning','email':'m@example.com'})
        self.assertEqual(code,200);self.assertEqual(calls[0]['line_items[0][price_data][unit_amount]'],'2200')
        self.assertIn('/download/morning-blessing.html',calls[0]['success_url'])

    def test_lead_capture(self):
        code,d=self.req('/api/lead',{'email':'reader@example.com','name':'Esther','source':'covenant'})
        self.assertEqual(code,200,d);self.assertTrue(d['ok'])
        with server.connection() as con:row=con.execute("SELECT * FROM leads WHERE email='reader@example.com'").fetchone()
        self.assertEqual(row['source'],'covenant')
        code,d=self.req('/api/lead',{'email':'not-an-email'});self.assertEqual(code,400)

if __name__=='__main__':unittest.main()

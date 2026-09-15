import unittest,tempfile,threading,urllib.request,urllib.error,http.cookiejar,json,time
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import server
from content import route
from http.server import ThreadingHTTPServer

def example(goal='calm'):
    a=dict(name='Alex',goal=goal,stage='retired',need='routine',feeling='content',experience='writing',time='5',style='balanced',pace='gentle',obstacle='cost',no_cost='journal',note='I would like a quiet morning routine without spending money.')
    a['focus']=route(a)[2]['options'][0]['value'];return a

class JourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();server.AI_ENABLED=False;server.VOICE_ENABLED=False
        server.EMAIL_RESOLVER=lambda domain: True
        server.init({'max_requests_per_minute':1000,'max_jobs_per_day':1000},cls.tmp.name,8101);cls.http=ThreadingHTTPServer(('127.0.0.1',8101),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
    def setUp(self):self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def req(self,path,data=None,client=None,headers=None,raw=False):
        h={'X-Requested-With':'RabbiDavid','Content-Type':'application/json'};h.update(headers or {})
        req=urllib.request.Request('http://127.0.0.1:8101'+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
        try:
            with (client or self.client).open(req,timeout=10) as r:status=r.status;content=r.read()
        except urllib.error.HTTPError as e:status=e.code;content=e.read()
        return status,content if raw else json.loads(content)
    def ready(self,goal='calm'):
        self.req('/api/enroll',dict(name='Alex',email='alex@example.com'));self.req('/api/save',dict(answers=example(goal),step=12));self.req('/api/generate',dict(consent=True))
        for _ in range(100):
            status,d=self.req('/api/state')
            if d['status']!='generating':return d
            time.sleep(.02)
        self.fail('generation did not finish')
    def test_complete_journey_and_no_repeat(self):
        d=self.ready();self.assertEqual(d['status'],'ready');self.assertEqual(len(d['reading']['sections']),1);self.assertIsNone(d['plan']);answers=d['answers']
        self.req('/api/contact',dict(email='alex@example.com',marketing=True))
        code,d=self.req('/api/demo-tier',dict(tier='reading'));self.assertEqual(code,200);self.assertEqual(len(d['reading']['sections']),4)
        self.req('/api/demo-tier',dict(tier='personal'))
        for _ in range(100):
            _,d=self.req('/api/state')
            if d.get('plan'):break
            time.sleep(.02)
        self.assertEqual(len(d['plan']),14);self.assertEqual(d['answers'],answers)
        _,d=self.req('/api/days',dict(days=[1,7]));self.assertEqual(d['completed_days'],[1,7])
        code,pdf=self.req('/api/pdf',raw=True);self.assertEqual(code,200);self.assertTrue(pdf.startswith(b'%PDF-'))
        Path(self.tmp.name,'test-reading.pdf').write_bytes(pdf)
        _,mails=self.req('/api/inbox');self.assertEqual(len([m for m in mails if m['kind'].startswith('followup')]),2)
        self.req('/api/demo-tier',dict(tier='personal'));_,after=self.req('/api/inbox');self.assertEqual(len(after),len(mails))
        self.req('/api/contact',dict(email='alex@example.com',marketing=False));_,mails=self.req('/api/inbox');self.assertFalse(any(m['kind'].startswith('followup') for m in mails))
    def test_session_isolation_and_full_content_gate(self):
        self.ready();self.req('/api/demo-tier',dict(tier='reading'))
        other=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        _,d=self.req('/api/state',client=other);self.assertIsNone(d['reading']);self.assertEqual(d['tier'],'free')
        self.assertEqual(self.req('/api/audio',client=other)[0],404);self.assertEqual(self.req('/api/transcript',client=other)[0],403)
        self.req('/api/new',{});_,d=self.req('/api/state');self.assertIsNone(d['reading'])

    def test_corrected_delivery_address_updates_local_outbox(self):
        self.ready()
        self.req('/api/contact',dict(email='corrected@example.com',marketing=True))
        _,messages=self.req('/api/inbox')
        self.assertTrue(messages)
        self.assertTrue(all(m['recipient']=='corrected@example.com' for m in messages))

    def test_random_text_rejected_and_existing_answer_can_be_corrected(self):
        d=self.ready();answers=d['answers'].copy();answers['note']='sdfjshfjksd'
        self.assertEqual(self.req('/api/save',dict(answers=answers,step=11))[0],400)
        with server.connection() as con:
            sid=con.execute('SELECT id FROM sessions ORDER BY updated DESC LIMIT 1').fetchone()['id']
        server.update(sid,lambda value:value['answers'].update(note='dscvd'))
        _,d=self.req('/api/state');self.assertEqual(d['answer_issues'][0]['id'],'note')
        self.assertEqual(self.req('/api/generate',dict(consent=True))[0],400)
        self.assertEqual(self.req('/api/demo-tier',dict(tier='reading'))[0],400)
        self.assertEqual(self.req('/api/save',dict(answers=d['answers'],step=11))[0],400)
        self.req('/api/new',{})
        self.req('/api/enroll',dict(name='Alex',email='alex@example.com'))
        answers=example();answers['note']=''
        code,corrected=self.req('/api/save',dict(answers=answers,step=12))
        self.assertEqual(code,200);self.assertEqual(corrected['answer_issues'],[])
        self.assertEqual(corrected['status'],'draft')
    def test_invalid_answers_consent_and_csrf(self):
        self.req('/api/enroll',dict(name='Alex',email='alex@example.com'));a=example();a['goal']='invented';self.assertEqual(self.req('/api/save',dict(answers=a))[0],400)
        self.assertEqual(self.req('/api/generate',dict(consent=True))[0],400)
        self.req('/api/save',dict(answers=example(),step=12));self.assertEqual(self.req('/api/generate',dict(consent=False))[0],400)
        self.assertEqual(self.req('/api/new',{},headers={'Origin':'https://untrusted.example'})[0],403)
        self.assertEqual(self.req('/api/demo-tier',dict(tier='personal'))[0],400)
    def test_adaptive_route_and_recommendation(self):
        calm=route(example('calm'));legacy=route(example('legacy'))
        self.assertNotEqual(calm[2]['title'],legacy[2]['title']);self.assertEqual(len(calm),12)
        a=example();a['obstacle']='none';self.assertEqual(len(route(a)),11)
        d=self.ready('legacy');self.assertEqual(d['recommendation']['book']['id'],'legacy')
        _,d=self.req('/api/owned',dict(owned=['legacy']));self.assertIsNone(d['recommendation'])
    def test_recovery_one_use(self):
        self.ready();self.req('/api/contact',dict(email='recover@example.com',marketing=False));self.req('/api/recover',dict(email='recover@example.com'))
        _,mails=self.req('/api/inbox');message=next(m for m in mails if m['kind']=='access');link=message['body'].splitlines()[0].split('Open ')[1]
        token=link.split('token=')[1]
        other=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with other.open(link) as response:self.assertEqual(response.status,200)
        _,d=self.req('/api/state',client=other);self.assertEqual(d['email'],'recover@example.com')
        self.assertEqual(self.req('/access?token='+token,raw=True)[0],400)
    def test_files_and_private_config(self):
        self.assertEqual(self.req('/config.json')[0],404);self.assertEqual(self.req('/server.py')[0],404)
        code,body=self.req('/css/style.css',raw=True);self.assertEqual(code,200);self.assertGreater(len(body),1000)

    def test_optional_followup_survives_and_invalidates(self):
        self.req('/api/enroll',dict(name='Alex',email='alex@example.com'));a=example();self.req('/api/save',dict(answers=a,step=12))
        self.assertEqual(self.req('/api/followup',dict(consent=False))[0],400)
        _,d=self.req('/api/followup',dict(consent=True));self.assertEqual(len(d['questions']),13)
        a['personal_detail']='An unhurried cup of tea and one page in my notebook.'
        _,d=self.req('/api/save',dict(answers=a,step=13));self.assertEqual(d['answers']['personal_detail'],a['personal_detail'])
        self.assertEqual(d['step'],13)
        a['obstacle']='none';_,d=self.req('/api/save',dict(answers=a,step=11))
        self.assertNotIn('followup',d);self.assertNotIn('personal_detail',d['answers'])

    def test_completed_test_requires_new_session_to_change_answers(self):
        before=self.ready()
        a=example();a['time']='10'
        self.assertEqual(self.req('/api/save',dict(answers=a,step=12))[0],400)
        _,current=self.req('/api/state');self.assertEqual(current['answers'],before['answers'])
        self.req('/api/new',{});self.req('/api/enroll',dict(name='Alex',email='alex@example.com'))
        self.assertEqual(self.req('/api/save',dict(answers=a,step=12))[0],200)
        _,current=self.req('/api/state');self.assertEqual(current['answers']['time'],'10')

    def test_voice_duplicate_clicks_only_submit_once(self):
        self.ready();self.req('/api/demo-tier',dict(tier='personal'))
        for _ in range(100):
            _,d=self.req('/api/state')
            if d.get('plan'):break
            time.sleep(.02)
        server.VOICE_ENABLED=True
        try:
            with patch.object(server,'submit_voice',return_value='mock-task-one') as submit:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results=list(pool.map(lambda _:self.req('/api/voice',{}),range(4)))
                for _ in range(100):
                    if submit.call_count:break
                    time.sleep(.02)
                self.assertTrue(all(code==200 for code,_ in results));self.assertEqual(submit.call_count,1)
                self.assertEqual(self.req('/api/save',dict(answers=example(),step=1))[0],400)
        finally:server.VOICE_ENABLED=False


    def test_identity_required_and_cannot_bypass(self):
        self.req('/api/state')
        for path,data in [('/api/save',dict(answers=example())),('/api/generate',dict(consent=True)),('/api/followup',dict(consent=True)),('/api/demo-tier',dict(tier='personal'))]:
            self.assertEqual(self.req(path,data)[0],403)
        for name,email in [('', 'a@example.com'),('Alex',''),('Alex','x@'),('Alex','a..b@example.com'),('<img>','a@example.com'),('123','a@example.com')]:
            self.assertEqual(self.req('/api/enroll',dict(name=name,email=email))[0],400)
        code,d=self.req('/api/enroll',dict(name=' Alex ',email='ALEX@EXAMPLE.COM'))
        self.assertEqual(code,200);self.assertTrue(d['started']);self.assertEqual(d['email'],'alex@example.com');self.assertFalse(d['marketing'])
        self.assertEqual(d['answers']['name'],'Alex')
        self.assertEqual(self.req('/api/save',dict(answers={'name':''}))[0],400)
        _,d=self.req('/api/enroll',dict(name='Other',email='other@example.com'))
        self.assertEqual(d['email'],'alex@example.com')
        self.req('/api/new',{})
        self.assertEqual(self.req('/api/save',dict(answers=example()))[0],403)

    def test_double_generate_and_upgrade_do_not_duplicate_jobs(self):
        self.req('/api/enroll',dict(name='Alex',email='alex@example.com'))
        self.req('/api/save',dict(answers=example(),step=12))
        with patch.object(server.POOL,'submit') as submit:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(lambda _:self.req('/api/generate',dict(consent=True)),range(4)))
            self.assertTrue(all(code==200 for code,_ in results));self.assertEqual(submit.call_count,1)
        # A fresh completed reflection permits precisely one plan job.
        self.req('/api/new',{});self.ready()
        with patch.object(server.POOL,'submit') as submit:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(lambda _:self.req('/api/demo-tier',dict(tier='personal')),range(4)))
            self.assertTrue(all(code==200 for code,_ in results));self.assertEqual(submit.call_count,1)

if __name__=='__main__':unittest.main(verbosity=2)

"""Free local review mode, isolated state and mocked voice/text services."""
import unittest
from unittest.mock import patch
import test_app,server
from content import draft_plan
from test_personalization import valid_reading

class FreeTestingTests(unittest.TestCase):
    setUpClass=classmethod(test_app.JourneyTests.setUpClass.__func__)
    tearDownClass=classmethod(test_app.JourneyTests.tearDownClass.__func__)
    req=test_app.JourneyTests.req
    def setUp(self):
        test_app.JourneyTests.setUp(self)
        server.CONFIG['free_testing']=True;server.VOICE_ENABLED=True;server.AI_ENABLED=False
        self.sid=server.new_session()
        server.update(self.sid,lambda d:d.update(started=True,email='alex@example.com',answers=test_app.example(),status='ready',source='ai',reading_version=2,reading=valid_reading()))
    def tearDown(self):
        server.CONFIG.pop('free_testing',None);server.VOICE_ENABLED=False;server.AI_ENABLED=False
    def request(self,path,data=None,raw=False):return self.req(path,data,headers={'Cookie':'rd_session='+self.sid},raw=raw)
    def test_invalid_answers_block_free_preview_without_work(self):
        server.update(self.sid,lambda d:d['answers'].update(note='asdfgh qwerty'))
        with patch.object(server.POOL,'submit') as submit:
            self.assertEqual(self.request('/api/free-preview',{})[0],400)
            submit.assert_not_called()
        self.assertEqual(server.get(self.sid)['tier'],'free')
    def test_disabled_flag_rejects(self):
        server.CONFIG['free_testing']=False
        self.assertEqual(self.request('/api/free-preview',{})[0],400)
    def test_repeat_preview_and_plan_completion_schedule_each_job_once(self):
        with patch.object(server.POOL,'submit') as submit:
            for _ in range(3):self.assertEqual(self.request('/api/free-preview',{})[0],200)
            jobs=[c.args[0] for c in submit.call_args_list]
            self.assertEqual(jobs.count(server.plan_job),1);self.assertEqual(jobs.count(server.intro_job),0);self.assertEqual(jobs.count(server.start_voice),0)
            server.plan_job(self.sid,server.get(self.sid)['revision'])
            server.queue_preview_audio(self.sid);self.request('/api/free-preview',{})
            jobs=[c.args[0] for c in submit.call_args_list]
            self.assertEqual(jobs.count(server.plan_job),1);self.assertEqual(jobs.count(server.intro_job),0);self.assertEqual(jobs.count(server.start_voice),1)
    def test_complete_content_and_pdf_visible_in_personal_preview(self):
        server.update(self.sid,lambda d:d.update(plan=draft_plan(d['answers'])))
        with patch.object(server.POOL,'submit'):
            code,d=self.request('/api/free-preview',{})
        self.assertEqual(code,200);self.assertEqual(d['tier'],'personal');self.assertEqual(len(d['reading']['sections']),4);self.assertEqual(len(d['plan']),14)
        code,pdf=self.request('/api/pdf',raw=True)
        self.assertEqual(code,200);self.assertTrue(pdf.startswith(b'%PDF-'))
    def test_voice_payload_contains_evidence_and_first_step_without_duplicate(self):
        server.update(self.sid,lambda d:d.update(tier='personal',plan=draft_plan(d['answers'])))
        with patch.object(server,'submit_voice',return_value='mock-voice') as submit:
            server.start_voice(self.sid);server.start_voice(self.sid)
        self.assertEqual(submit.call_count,1);script=submit.call_args.args[1];reading=valid_reading()
        for item in reading['evidence']:self.assertIn(item['interpretation'],script)
        for value in reading['first_step'].values():self.assertIn(value,script)
    def test_generate_sets_personal_tier_without_checkout(self):
        server.update(self.sid,lambda d:d.update(status='draft',reading=None,source=None))
        with patch.object(server.POOL,'submit') as submit:
            code,d=self.request('/api/generate',{'consent':True})
        self.assertEqual(code,200);self.assertEqual(d['tier'],'personal');self.assertTrue(d['auto_audio']);self.assertEqual(d['status'],'generating')
        self.assertEqual(submit.call_count,1)

if __name__=='__main__':unittest.main(verbosity=2)

import json,unittest
from io import BytesIO
from email import policy
from email.parser import BytesParser
from unittest.mock import patch
from pypdf import PdfReader
import server,test_app
from content import draft_plan,fallback_reading

class PlanDeliveryTests(unittest.TestCase):
    setUpClass=classmethod(test_app.JourneyTests.setUpClass.__func__)
    tearDownClass=classmethod(test_app.JourneyTests.tearDownClass.__func__)
    req=test_app.JourneyTests.req
    def setUp(self):
        test_app.JourneyTests.setUp(self)
        self.sid=server.new_session();a=test_app.example()
        server.update(self.sid,lambda d:d.update(started=True,email='alex@example.com',answers=a,status='ready',tier='personal',reading=fallback_reading(a),plan=draft_plan(a)))
    def request(self,path,raw=False):return self.req(path,headers={'Cookie':'rd_session='+self.sid},raw=raw)
    def test_plan_pdf_and_actual_email_attachment_are_identical(self):
        server.prepare_plan_delivery(self.sid)
        status,pdf=self.request('/api/plan-pdf',raw=True)
        self.assertEqual(status,200);self.assertEqual(len(PdfReader(BytesIO(pdf)).pages),18)
        _,messages=self.request('/api/inbox');item=next(m for m in messages if m['kind']=='plan')
        status,eml=self.request(item['attachment_preview'],raw=True);self.assertEqual(status,200)
        msg=BytesParser(policy=policy.default).parsebytes(eml)
        attachments=list(msg.iter_attachments());self.assertEqual(len(attachments),1)
        attached=PdfReader(BytesIO(attachments[0].get_payload(decode=True)))
        self.assertEqual(len(attached.pages),18)
        self.assertEqual(msg['To'],'alex@example.com')
        self.assertEqual(attached.pages[2].extract_text(),PdfReader(BytesIO(pdf)).pages[2].extract_text())
    def test_other_session_cannot_read_email_or_plan(self):
        server.prepare_plan_delivery(self.sid)
        _,messages=self.request('/api/inbox');url=next(m for m in messages if m['kind']=='plan')['attachment_preview']
        self.assertEqual(self.req(url,raw=True)[0],404)
        self.assertEqual(self.req('/api/plan-pdf',raw=True)[0],403)
    def test_incomplete_plan_is_not_downloaded(self):
        server.update(self.sid,lambda d:d.update(plan=None))
        self.assertEqual(self.request('/api/plan-pdf')[0],409)
    def test_new_sources_are_hydrated_only_from_library(self):
        def change(d):d['reading']['sections'][0]['source_id']='avot_4_1';d['reading']['sections'][0]['source']={'url':'https://untrusted.invalid'}
        server.update(self.sid,change)
        state=server.safe_state(server.get(self.sid))
        self.assertEqual(state['reading']['sections'][0]['source']['title'],'Pirkei Avot 4:1')

    def test_retry_plan_preserves_answers_and_schedules_once(self):
        original=server.get(self.sid)['answers']
        server.update(self.sid,lambda d:d.update(plan_source='guided',plan_status='guided_alternative'))
        with patch.object(server,'AI_ENABLED',True),patch.object(server.POOL,'submit') as submit:
            for _ in range(2):
                status,_=self.req('/api/plan-retry',{'consent':True},headers={'Cookie':'rd_session='+self.sid})
                self.assertEqual(status,200)
            self.assertEqual(submit.call_count,1)
        self.assertEqual(server.get(self.sid)['answers'],original)
        self.assertIsNotNone(server.get(self.sid)['plan'])

    def test_retry_does_not_replace_a_started_plan(self):
        server.update(self.sid,lambda d:d.update(plan_source='guided',completed_days=[1]))
        with patch.object(server,'AI_ENABLED',True),patch.object(server.POOL,'submit') as submit:
            status,_=self.req('/api/plan-retry',{'consent':True},headers={'Cookie':'rd_session='+self.sid})
            self.assertEqual(status,400);submit.assert_not_called()

if __name__=='__main__':unittest.main()

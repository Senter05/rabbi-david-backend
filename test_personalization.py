"""Personalization contract tests. All providers are mocked; no credits are used."""
import json,time,unittest
from unittest.mock import patch
import providers,server
from content import route,fallback_reading
import test_app
from test_app import example

def valid_reading():
    paragraph=' '.join(['A thoughtful example connects a small morning practice with the time you chose and invites you to notice what feels useful today.']*4)
    return dict(title='A quieter direction for your morning',summary=paragraph,insight=paragraph,
      sections=[dict(title='Perspective '+str(i),text=paragraph) for i in range(4)],
      evidence=[dict(answer_ids=['goal','time'],interpretation='Your preference for calm and a short daily practice may work together by keeping the first step modest enough to return to tomorrow.'),dict(answer_ids=['experience','note'],interpretation='Your enjoyment of writing and your request to avoid spending could support a simple notebook reflection using materials you already have nearby.')],
      first_step=dict(action='Before your usual morning activity, spend five minutes writing one sentence about what deserves your attention today, using paper you already have, then choose one small action that reflects it.',why='This connects your preference for writing with the short practice and no spending approach you described.',reflection='What would help you return to this simple practice tomorrow?'))

class ValidationTests(unittest.TestCase):
    def test_provider_sends_question_labels_and_written_response(self):
        a=example();a.update(personal_detail='I enjoy tea on the porch.',personal_question='What would your calm morning look like?')
        from test_deep_reading import deep_reading, response
        complete=deep_reading()
        opening={key:value for key,value in complete.items() if key not in ('sections','evidence')};opening.update(connection_1=complete['evidence'][0]['interpretation'],connection_2=complete['evidence'][1]['interpretation'])
        responses=[response(opening)]+[response(dict(title=section['title'],text=section['text'])) for section in complete['sections']]
        with patch.object(providers,'request_json',side_effect=responses) as request:
            providers.generate_reading({'openrouter_key':'test-only'},a,fallback_reading(a))
        self.assertEqual(request.call_count,5)
        payload=json.loads(request.call_args_list[0].kwargs['data']);record=json.loads(payload['messages'][1]['content'])['questionnaire']
        for call in request.call_args_list[1:]:
            self.assertEqual(json.loads(json.loads(call.kwargs['data'])['messages'][1]['content'])['questionnaire'],record)
        mapped={r['id']:r for r in record}
        for question in route(a):
            self.assertEqual(mapped[question['id']]['question'],question['title'])
            if question.get('options'):
                label=next(o['label'] for o in question['options'] if o['value']==a[question['id']])
                self.assertEqual(mapped[question['id']]['answer'],label)
        self.assertEqual(mapped['personal_detail']['question'],a['personal_question'])
        self.assertEqual(mapped['personal_detail']['answer'],a['personal_detail'])
    def test_valid_grounding_passes(self):providers.validate_personal_reading(valid_reading(),example())
    def test_rejects_unsupported_answer_reference(self):
        obj=valid_reading();obj['evidence'][0]['answer_ids'][0]='invented_debt'
        with self.assertRaises(providers.ProviderError):providers.validate_personal_reading(obj,example())
    def test_rejects_ignored_written_answer(self):
        obj=valid_reading();obj['evidence'][1]['answer_ids']=['experience','pace']
        with self.assertRaises(providers.ProviderError):providers.validate_personal_reading(obj,example())
    def test_rejects_short_generic_sections(self):
        obj=valid_reading()
        for s in obj['sections']:s['text']='Take a quiet moment and reflect on abundance.'
        with self.assertRaises(providers.ProviderError):providers.validate_personal_reading(obj,example())
    def test_rejects_generic_first_step(self):
        obj=valid_reading();obj['first_step']['action']='Be more grateful today.'
        with self.assertRaises(providers.ProviderError):providers.validate_personal_reading(obj,example())

class RefreshTests(unittest.TestCase):
    setUpClass=classmethod(test_app.JourneyTests.setUpClass.__func__)
    tearDownClass=classmethod(test_app.JourneyTests.tearDownClass.__func__)
    setUp=test_app.JourneyTests.setUp
    req=test_app.JourneyTests.req
    ready=test_app.JourneyTests.ready
    def tearDown(self):server.AI_ENABLED=False
    def test_refresh_guided_preserves_answers_tier_and_valid_reading_is_idempotent(self):
        before=self.ready();self.req('/api/demo-tier',dict(tier='reading'));server.AI_ENABLED=True
        with patch.object(server,'generate_reading',return_value=(valid_reading(),{})) as generate:
            code,d=self.req('/api/generate',dict(consent=True,refresh=True))
            self.assertEqual(code,200)
            for _ in range(100):
                _,d=self.req('/api/state')
                if d['status']!='generating':break
                time.sleep(.02)
            self.assertEqual(d['status'],'ready');self.assertEqual(d['reading_version'],3);self.assertEqual(d['source'],'ai')
            self.assertEqual(d['answers'],before['answers']);self.assertEqual(d['tier'],'reading')
            self.req('/api/generate',dict(consent=True,refresh=True))
            self.assertEqual(generate.call_count,1)
    def test_guided_upgrade_blocked_when_ai_enabled(self):
        self.ready();server.AI_ENABLED=True
        code,_=self.req('/api/demo-tier',dict(tier='reading'))
        self.assertEqual(code,400)

if __name__=='__main__':unittest.main(verbosity=2)

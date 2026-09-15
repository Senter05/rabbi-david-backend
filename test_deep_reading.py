"""Detailed reading and teaching-plan contracts; mock providers only."""
import copy,json,unittest
from unittest.mock import patch
import providers
from content import draft_plan
from source_library import SOURCES
from content import route

def example():
    a=dict(name='Alex',goal='calm',stage='retired',need='routine',feeling='content',experience='writing',time='5',style='balanced',pace='gentle',obstacle='cost',no_cost='journal',note='I prefer quiet mornings without spending money.')
    a['focus']=route(a)[2]['options'][0]['value']
    return a

def valid_reading():
    return dict(title='Thoughtful everyday practice',summary=words(60),insight=words(40),sections=[dict(title='Perspective '+str(i),text=words(90)) for i in range(4)],evidence=[dict(answer_ids=['goal','note'],interpretation=words(30)),dict(answer_ids=['time','experience'],interpretation=words(30))],first_step=dict(action=words(40),why=words(25),reflection=words(10)+'?'))

def words(number):
    return ' '.join(('Thoughtful reflection connects practical choices with gratitude care responsibility purpose and the life you described today'.split()*number)[:number])

def deep_reading():
    d=valid_reading();d['summary']=words(130);d['insight']=words(90)
    for i,s in enumerate(d['sections']):
        s.update(text=words(100)+'\n\n'+words(100)+'\n\n'+words(100)+'\n\n'+words(100),source_id=SOURCES[i]['id'])
    for item in d['evidence']:item['interpretation']=words(50)
    d['first_step']=dict(action=words(75),why=words(40),reflection=words(12)+'?')
    return d

def batch(start):
    return [dict(day=i,title='A thoughtful practice '+str(i),minutes=5,teaching=words(120),why=words(55),source_id=SOURCES[(i-1)%len(SOURCES)]['id'],action=words(75),reflection=words(12)+'?',adaptation=words(40)) for i in range(start,start+7)]

def response(obj):return dict(choices=[dict(message=dict(content=json.dumps(obj)))],usage={})

class DeepReadingTests(unittest.TestCase):
    def test_complete_reading_has_validated_sources_and_long_form_limits(self):
        d=deep_reading();opening={k:v for k,v in d.items() if k not in ('sections','evidence')};opening.update(connection_1=d['evidence'][0]['interpretation'],connection_2=d['evidence'][1]['interpretation']);progress=[]
        responses=[response(opening)]+[response(dict(title=s['title'],text=s['text'])) for s in d['sections']]
        with patch.object(providers,'request_json',side_effect=responses) as request:
            result,usage=providers.generate_reading({'openrouter_key':'mock'},example(),{},progress=lambda completed,total:progress.append((completed,total)))
        self.assertEqual(len(result['sections']),4);self.assertEqual(request.call_count,5)
        self.assertTrue(all(call.kwargs['timeout']==60 for call in request.call_args_list))
        self.assertEqual(progress,[(1,5),(2,5),(3,5),(4,5),(5,5)])
        self.assertEqual(usage['generation_mode'],'staged')
        self.assertTrue(all('\n\n' in s['text'] for s in result['sections']))
    def test_invalid_fragment_retries_only_that_fragment(self):
        d=deep_reading();opening={k:v for k,v in d.items() if k not in ('sections','evidence')};opening.update(connection_1=d['evidence'][0]['interpretation'],connection_2=d['evidence'][1]['interpretation'])
        responses=[response(opening),response({'title':'Too brief','text':'Not enough.'})]+[response(dict(title=s['title'],text=s['text'])) for s in d['sections']]
        with patch.object(providers,'request_json',side_effect=responses) as request:
            result,usage=providers.generate_reading({'openrouter_key':'mock'},example(),{})
        self.assertEqual(request.call_count,6);self.assertEqual(usage['attempts'],6)
        self.assertEqual(result['summary'],opening['summary'])
    def test_trailing_comma_parser_preserves_strings_and_rejects_truncated_json(self):
        obj=providers.parse_model_json('{"text":"inside,} and escaped \\"quote\\"", "items":[1,2,],}')
        self.assertEqual(obj['text'],'inside,} and escaped "quote"');self.assertEqual(obj['items'],[1,2])
        with self.assertRaises(providers.ProviderError):providers.parse_model_json('{"text":"unfinished')
    def test_paragraph_array_is_assembled_and_ids_are_server_assigned(self):
        d=deep_reading();opening={k:v for k,v in d.items() if k not in ('sections','evidence')}
        opening.update(connection_1=d['evidence'][0]['interpretation'],connection_2=d['evidence'][1]['interpretation'],evidence=[{'answer_ids':['invented']}])
        responses=[response(opening)]+[response(dict(title=section['title'],paragraphs=[words(58)]*7,source_id='invented')) for section in d['sections']]
        with patch.object(providers,'request_json',side_effect=responses):
            result,_=providers.generate_reading({'openrouter_key':'mock'},example(),{})
        self.assertEqual(result['evidence'][0]['answer_ids'],['goal','note'])
        self.assertEqual(result['evidence'][1]['answer_ids'],['time','experience'])
        self.assertEqual(len(result['sections'][0]['text'].split()),406)
        self.assertNotEqual(result['sections'][0]['source_id'],'invented')
    def test_rate_limit_is_not_retried_immediately(self):
        with patch.object(providers,'request_json',side_effect=providers.ProviderError('Provider returned HTTP 429')) as request:
            with self.assertRaises(providers.ProviderError):providers.generate_reading({'openrouter_key':'mock'},example(),{})
            self.assertEqual(request.call_count,1)
    def test_legacy_validation_stays_compatible_but_new_generation_gate_rejects_short(self):
        old=valid_reading();providers.validate_personal_reading(old,example())
        for section in old['sections']:section['source_id']=SOURCES[0]['id']
        with self.assertRaises(providers.ProviderError):providers.validate_deep_reading(old,SOURCES)
    def test_unlisted_source_is_rejected(self):
        d=deep_reading();d['sections'][0]['source_id']='invented_source'
        with self.assertRaises(providers.ProviderError):providers.validate_deep_reading(d,SOURCES)
    def test_plan_uses_two_complete_batches_with_continuity(self):
        with patch.object(providers,'request_json',side_effect=[response({'days':batch(1)}),response({'days':batch(8)})]) as request:
            days=providers.generate_plan({'openrouter_key':'mock'},example(),draft_plan(example()))
        self.assertEqual([d['day'] for d in days],list(range(1,15)));self.assertEqual(request.call_count,2)
        payloads=[json.loads(c.kwargs['data']) for c in request.call_args_list]
        second=json.loads(payloads[1]['messages'][1]['content'])
        self.assertEqual(second['day_numbers'],list(range(8,15)));self.assertEqual(len(second['previous_days']),7)
        self.assertTrue(all(p['max_tokens']==7000 for p in payloads))
        self.assertTrue(all(c.kwargs['timeout']==120 for c in request.call_args_list))
    def test_plan_rejects_short_teaching_wrong_source_and_wrong_day(self):
        for key,value in [('teaching','A generic idea.'),('day',9),('minutes',15)]:
            invalid=batch(1);invalid[0][key]=value
            with self.subTest(key=key),patch.object(providers,'request_json',return_value=response({'days':invalid})) as request:
                with self.assertRaises(providers.ProviderError):providers.generate_plan({'openrouter_key':'mock'},example(),draft_plan(example()))
                self.assertEqual(request.call_count,1)

if __name__=='__main__':unittest.main(verbosity=2)

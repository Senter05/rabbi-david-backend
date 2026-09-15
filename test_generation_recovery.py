"""Exercise the actual staged generation contract without a network."""
import unittest
from unittest.mock import patch
import providers
from test_deep_reading import example,deep_reading,response

def replies():
    d=deep_reading();opening={k:v for k,v in d.items() if k not in ('sections','evidence')}
    opening.update(connection_1=d['evidence'][0]['interpretation'],connection_2=d['evidence'][1]['interpretation'])
    return [response(opening)]+[response(dict(title=s['title'],text=s['text'])) for s in d['sections']]

class RecoveryTests(unittest.TestCase):
    def test_invalid_response_is_corrected_once(self):
        sequence=replies();sequence.insert(1,response({'title':'Too short','text':'Invalid'}))
        with patch.object(providers,'request_json',side_effect=sequence) as call:
            result,usage=providers.generate_reading({'openrouter_key':'mock'},example(),{})
        self.assertEqual(call.call_count,6);self.assertEqual(usage['attempts'],6);self.assertEqual(len(result['sections']),4)
    def test_persistent_failure_stops_after_two(self):
        with patch.object(providers,'request_json',return_value=response({'title':'Incomplete'})) as call:
            with self.assertRaises(providers.ProviderError):providers.generate_reading({'openrouter_key':'mock'},example(),{})
        self.assertEqual(call.call_count,2)
    def test_auth_failure_is_not_retried(self):
        with patch.object(providers,'request_json',side_effect=providers.ProviderError('Provider returned HTTP 401')) as call:
            with self.assertRaises(providers.ProviderError):providers.generate_reading({'openrouter_key':'mock'},example(),{})
        self.assertEqual(call.call_count,1)
    def test_success_does_not_retry(self):
        with patch.object(providers,'request_json',side_effect=replies()) as call:
            _,usage=providers.generate_reading({'openrouter_key':'mock'},example(),{})
        self.assertEqual(call.call_count,5);self.assertEqual(usage['attempts'],5)
    def test_json_array_is_rejected_cleanly(self):
        with patch.object(providers,'request_json',return_value=response([])):
            with self.assertRaises(providers.ProviderError):providers.generate_reading({'openrouter_key':'mock'},example(),{})
if __name__=='__main__':unittest.main()

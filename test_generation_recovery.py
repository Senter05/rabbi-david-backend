"""Recovery tests: no network and no provider credits."""
import unittest
from unittest.mock import patch
import providers
from test_personalization import valid_reading
from test_app import example
from content import fallback_reading
class RecoveryTests(unittest.TestCase):
 def test_invalid_response_is_corrected_once(self):
  with patch.object(providers,'_generate_reading_once',side_effect=[providers.ProviderError('Written response not considered'),(valid_reading(),{})]) as call:
   r,u=providers.generate_reading({},example(),{})
  self.assertEqual(u['attempts'],2);self.assertEqual(call.call_args.args[-1],'Written response not considered')
 def test_persistent_failure_stops_after_two(self):
  with patch.object(providers,'_generate_reading_once',side_effect=providers.ProviderError('Incomplete reading')) as call:
   with self.assertRaises(providers.ProviderError):providers.generate_reading({},example(),{})
  self.assertEqual(call.call_count,2)
 def test_auth_failure_is_not_retried(self):
  with patch.object(providers,'_generate_reading_once',side_effect=providers.ProviderError('Provider returned HTTP 401')) as call:
   with self.assertRaises(providers.ProviderError):providers.generate_reading({},example(),{})
  self.assertEqual(call.call_count,1)
 def test_success_does_not_retry(self):
  with patch.object(providers,'_generate_reading_once',return_value=(valid_reading(),{})) as call:
   _,u=providers.generate_reading({},example(),{})
  self.assertEqual(call.call_count,1);self.assertEqual(u['attempts'],1)
 def test_json_array_is_rejected_cleanly(self):
  with patch.object(providers,'request_json',return_value={'choices':[{'message':{'content':'[]'}}]}):
   with self.assertRaises(providers.ProviderError):providers.generate_reading({'openrouter_key':'test'},example(),fallback_reading(example()))
if __name__=='__main__':unittest.main()

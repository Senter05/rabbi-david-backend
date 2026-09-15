import unittest
from unittest.mock import patch
import input_validation as validation

class ContactTests(unittest.TestCase):
    def test_normalizes_and_sends_domain_only_to_resolver(self):
        seen=[]
        self.assertEqual(validation.validate_contact_email('  Alex+Reading@GMAIL.COM ',resolver=lambda domain:seen.append(domain) or True),'alex+reading@gmail.com')
        self.assertEqual(seen,['gmail.com'])
    def test_bad_syntax_and_typo_do_not_query_dns(self):
        with patch.object(validation,'domain_accepts_mail') as resolver:
            for value in ['',None,'a@@gmail.com','.a@gmail.com','a..b@gmail.com','a.@gmail.com','a@-gmail.com','a@gmail..com','a@localhost','a@gamil.com','a@gmail.con','a\n@gmail.com']:
                with self.subTest(value=value),self.assertRaises(ValueError):validation.validate_contact_email(value)
            resolver.assert_not_called()
    def test_nonexistent_domain_rejected(self):
        with self.assertRaises(ValueError):validation.validate_contact_email('alex@missing.test',resolver=lambda domain:False)
    def test_international_domain_is_encoded(self):
        seen=[]
        validation.validate_contact_email('alex@mañana.es',resolver=lambda domain:seen.append(domain) or True)
        self.assertEqual(seen,['xn--maana-pta.es'])
    def test_dns_cache_and_null_mx(self):
        validation._CACHE.clear()
        with patch.object(validation,'_dns_query',return_value={'Status':0,'Answer':[{'type':15,'data':'0 .'}]}) as query:
            self.assertFalse(validation.domain_accepts_mail('null.example'))
            self.assertFalse(validation.domain_accepts_mail('null.example'))
            self.assertEqual(query.call_count,1)
    def test_valid_mx_and_implicit_mx(self):
        validation._CACHE.clear()
        with patch.object(validation,'_dns_query',return_value={'Status':0,'Answer':[{'type':15,'data':'10 mx.example.'}]}):
            self.assertTrue(validation.domain_accepts_mail('mx.example'))
        with patch.object(validation,'_dns_query',side_effect=[{'Status':0,'Answer':[]},{'Status':0,'Answer':[{'type':1,'data':'192.0.2.1'}]}]):
            self.assertTrue(validation.domain_accepts_mail('implicit.example'))

class WrittenTests(unittest.TestCase):
    def test_blank_optional_and_normalization(self):
        self.assertEqual(validation.validate_written_answer(' \n '),'')
        self.assertEqual(validation.validate_written_answer('  More   peace\nplease '),'More peace please')
    def test_real_short_and_technical_answers(self):
        for value in ['More peace','Quiero más tranquilidad','My strengths include SQL and CSS','I work with PostgreSQL databases','HTTPS SSL configuration','Mi mamá necesita apoyo','I feel fine','Less stress','משפחה טובה']:
            with self.subTest(value=value):self.assertEqual(validation.validate_written_answer(value),value)
    def test_rejects_unusable_inputs(self):
        for value in ['sdfjshfjksd','123456 9999','a b','aaaaaa aaaaaa','hello hello hello','qwerty asdfgh','sdfjshfjksd fghjklmn']:
            with self.subTest(value=value),self.assertRaises(ValueError):validation.validate_written_answer(value)

if __name__=='__main__':unittest.main(verbosity=2)

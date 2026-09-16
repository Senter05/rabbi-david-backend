"""Authentication regressions using isolated storage and no listening socket."""
import io,json,tempfile,unittest
from unittest.mock import patch
import server

class AuthOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        server.init({'max_requests_per_minute':1000},self.tmp.name,8199)
        self.resolver=patch.object(server,'EMAIL_RESOLVER',lambda domain:True)
        self.resolver.start()
    def tearDown(self):
        self.resolver.stop();self.tmp.cleanup()
    def request(self,path,body,sid=None):
        sid=sid or server.new_session()
        h=object.__new__(server.Handler)
        payload=json.dumps(body).encode()
        h.path=path;h.headers={'X-Requested-With':'RabbiDavid','Content-Length':str(len(payload))}
        h.rfile=io.BytesIO(payload);h.client_address=('127.0.0.1',1)
        h.allowed_host=lambda:True;h.allowed_origin=lambda:True;h.session=lambda:sid
        h.new_cookie=None
        reply={}
        def send(status=200,obj=None,*args,**kwargs):reply.update(status=status,body=obj)
        h.send=send
        with patch.object(server,'mail_configured',return_value=False),patch.object(server.SUPABASE,'is_configured',return_value=False):h.do_POST()
        return reply,sid,h.new_cookie
    def owner(self,sid):
        with server.connection() as con:return con.execute('SELECT user_id FROM sessions WHERE id=?',(sid,)).fetchone()['user_id']
    def test_existing_account_cannot_be_enrolled_without_password(self):
        user,_=server.create_or_get_user('owner@example.com','OwnerPassword123','Owner')
        for password in [None,'','WrongPassword123']:
            body={'name':'Intruder','email':user['email']}
            if password is not None:body['password']=password
            response,sid,_=self.request('/api/enroll',body)
            self.assertEqual(response['status'],400)
            self.assertFalse(self.owner(sid));self.assertFalse(server.get(sid)['started'])
    def test_legacy_passwordless_account_requires_mail_recovery_not_arbitrary_password(self):
        user,_=server.create_or_get_user('legacy@example.com',None,'Legacy')
        for path in ['/api/enroll','/api/auth/register']:
            response,sid,_=self.request(path,{'name':'Intruder','email':user['email'],'password':'ChosenPassword123'})
            self.assertEqual(response['status'],400);self.assertFalse(self.owner(sid))
        self.assertFalse(server.get_user_by_id(user['id'])['password_hash'])
    def test_registration_does_not_claim_legacy_readings_by_matching_email(self):
        legacy=server.new_session()
        server.update(legacy,lambda d:d.update(email='new@example.com',started=True))
        response,sid,_=self.request('/api/auth/register',{'name':'New','email':'new@example.com','password':'NewPassword123'})
        self.assertEqual(response['status'],200);self.assertTrue(self.owner(sid));self.assertFalse(self.owner(legacy))
        self.assertNotIn(legacy,[r['id'] for r in response['body']['readings']])
    def test_login_does_not_claim_matching_email_session_owned_by_another_account(self):
        first,_=server.create_or_get_user('first@example.com','FirstPassword123','First')
        second,_=server.create_or_get_user('second@example.com','SecondPassword123','Second')
        saved=server.new_session();server.update(saved,lambda d:d.update(email=second['email'],started=True))
        server.link_user_sessions(first['id'],first['email'],saved)
        response,sid,_=self.request('/api/auth/login',{'email':second['email'],'password':'SecondPassword123'})
        self.assertEqual(response['status'],200);self.assertEqual(self.owner(saved),first['id'])
        self.assertEqual(self.owner(sid),second['id'])
        self.assertNotIn(saved,[r['id'] for r in response['body']['readings']])
    def test_switching_account_uses_new_session_without_reassigning_old_reading(self):
        first,_=server.create_or_get_user('first@example.com','FirstPassword123','First')
        second,_=server.create_or_get_user('second@example.com','SecondPassword123','Second')
        saved=server.new_session();server.link_user_sessions(first['id'],first['email'],saved)
        response,_,new_sid=self.request('/api/auth/login',{'email':second['email'],'password':'SecondPassword123'},saved)
        self.assertEqual(response['status'],200);self.assertTrue(new_sid)
        self.assertEqual(self.owner(saved),first['id']);self.assertEqual(self.owner(new_sid),second['id'])
    def test_correct_password_enroll_links_only_current_session(self):
        user,_=server.create_or_get_user('owner@example.com','OwnerPassword123','Owner')
        legacy=server.new_session();server.update(legacy,lambda d:d.update(email=user['email'],started=True))
        response,sid,_=self.request('/api/enroll',{'name':'Owner','email':user['email'],'password':'OwnerPassword123'})
        self.assertEqual(response['status'],200);self.assertEqual(self.owner(sid),user['id'])
        self.assertFalse(self.owner(legacy))

if __name__=='__main__':unittest.main()

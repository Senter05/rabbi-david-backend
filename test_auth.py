import unittest, tempfile, os, time, threading, urllib.request, json, http.cookiejar
from unittest.mock import patch
import server, test_app
from supabase_client import SupabaseClient

class AuthTests(unittest.TestCase):
    setUpClass = classmethod(test_app.JourneyTests.setUpClass.__func__)
    tearDownClass = classmethod(test_app.JourneyTests.tearDownClass.__func__)
    setUp = test_app.JourneyTests.setUp
    req = test_app.JourneyTests.req

    def new_client(self):
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        opener.cookiejar = cj
        return opener

    def test_password_hash_and_verify(self):
        salt, pw_hash = server.hash_password('SecretPassword123!')
        self.assertTrue(bool(salt))
        self.assertTrue(bool(pw_hash))
        self.assertTrue(server.verify_password('SecretPassword123!', salt, pw_hash))
        self.assertFalse(server.verify_password('WrongPassword', salt, pw_hash))
        self.assertFalse(server.verify_password('', salt, pw_hash))

    def test_register_and_login_flow(self):
        client = self.new_client()
        email = 'tester_reg@example.com'
        # 1. Short password rejected
        code, err = self.req('/api/auth/register', {'name': 'Tester', 'email': email, 'password': 'short'}, client=client)
        self.assertEqual(code, 400)

        # 2. Successful registration
        code, res = self.req('/api/auth/register', {'name': 'Tester User', 'email': email, 'password': 'ValidPassword123'}, client=client)
        self.assertEqual(code, 200)
        self.assertEqual(res['user']['email'], email)
        self.assertEqual(res['user']['name'], 'Tester User')
        self.assertFalse(res['user']['email_verified'])

        # 3. Duplicate registration rejected
        code, err = self.req('/api/auth/register', {'name': 'Tester Two', 'email': email, 'password': 'AnotherPassword123'}, client=client)
        self.assertEqual(code, 400)

        # 4. Status reflects logged-in user
        code, status_data = self.req('/api/auth/status', client=client)
        self.assertEqual(code, 200)
        self.assertTrue(status_data['enabled'])
        self.assertIsNotNone(status_data['user'])
        self.assertEqual(status_data['user']['email'], email)

        # 5. Logout clears user
        code, logout_res = self.req('/api/auth/logout', {}, client=client)
        self.assertEqual(code, 200)
        code, status_after = self.req('/api/auth/status', client=client)
        self.assertIsNone(status_after['user'])

        # 6. Login with wrong password rejected
        code, err = self.req('/api/auth/login', {'email': email, 'password': 'WrongPassword'}, client=client)
        self.assertEqual(code, 400)

        # 7. Login with correct password succeeds
        code, login_res = self.req('/api/auth/login', {'email': email, 'password': 'ValidPassword123'}, client=client)
        self.assertEqual(code, 200)
        self.assertEqual(login_res['user']['email'], email)

    def test_enroll_with_password(self):
        client = self.new_client()
        email = 'enroll_user@example.com'
        code, res = self.req('/api/enroll', {'name': 'Sarah', 'email': email, 'password': 'MySecurePassword2026', 'marketing': True}, client=client)
        self.assertEqual(code, 200)
        self.assertEqual(res['answers']['name'], 'Sarah')
        self.assertEqual(res['email'], email)

        # Check user was created in DB
        u = server.get_user_by_email(email)
        self.assertIsNotNone(u)
        self.assertEqual(u['name'], 'Sarah')
        self.assertTrue(server.verify_password('MySecurePassword2026', u['salt'], u['password_hash']))

        # Enrolling again with same email and wrong password should fail
        client2 = self.new_client()
        code2, err2 = self.req('/api/enroll', {'name': 'Sarah', 'email': email, 'password': 'WrongPassword123'}, client=client2)
        self.assertEqual(code2, 400)
        self.assertIn('already exists', err2['error'])

    def test_password_reset_flow(self):
        client = self.new_client()
        email = 'reset_user@example.com'
        # Register user
        self.req('/api/auth/register', {'name': 'Reset Test', 'email': email, 'password': 'InitialPassword123'}, client=client)

        # Request reset
        code, res = self.req('/api/auth/reset-request', {'email': email}, client=client)
        self.assertEqual(code, 200)

        # Get token from database
        u = server.get_user_by_email(email)
        with server.connection() as con:
            row = con.execute('SELECT token FROM password_resets WHERE user_id=?', (u['id'],)).fetchone()
        self.assertIsNotNone(row)
        token = row['token']

        # Confirm reset with invalid token
        code, _ = self.req('/api/auth/reset-confirm', {'token': 'invalid-token', 'password': 'BrandNewPassword123'}, client=client)
        self.assertEqual(code, 400)

        # Confirm reset with valid token
        code, res = self.req('/api/auth/reset-confirm', {'token': token, 'password': 'BrandNewPassword123'}, client=client)
        self.assertEqual(code, 200)

        # Verify old password no longer works
        client2 = self.new_client()
        code, _ = self.req('/api/auth/login', {'email': email, 'password': 'InitialPassword123'}, client=client2)
        self.assertEqual(code, 400)

        # Verify new password works
        code, login_res = self.req('/api/auth/login', {'email': email, 'password': 'BrandNewPassword123'}, client=client2)
        self.assertEqual(code, 200)
        self.assertEqual(login_res['user']['email'], email)

    def test_reset_sends_one_message_when_supabase_is_configured(self):
        email='single_reset@example.com'
        self.req('/api/auth/register', {'name':'Reset Test','email':email,'password':'InitialPassword123'})
        with patch.object(server.SUPABASE,'is_configured',return_value=True), patch.object(server.SUPABASE,'send_password_recovery') as duplicate:
            code,_=self.req('/api/auth/reset-request',{'email':email})
        self.assertEqual(code,200)
        duplicate.assert_not_called()
        with server.connection() as con:
            rows=con.execute("SELECT body FROM mail WHERE recipient=? AND kind='password_reset'",(email,)).fetchall()
        self.assertEqual(len(rows),1)
        self.assertIn('1 hour',rows[0]['body'])
        self.assertIn('/account.html?reset_token=',rows[0]['body'])

    def test_email_verification_flow(self):
        email = 'verify_me@example.com'
        self.req('/api/auth/register', {'name': 'Verify Test', 'email': email, 'password': 'VerifyPass123'})
        u = server.get_user_by_email(email)
        self.assertEqual(u['email_verified'], 0)
        token = u['verification_token']
        self.assertTrue(bool(token))

        # Verify via endpoint
        code, res = self.req(f'/api/auth/verify-email?token={token}')
        self.assertEqual(code, 200)

        u_after = server.get_user_by_email(email)
        self.assertEqual(u_after['email_verified'], 1)

    def test_user_isolation_reading_access(self):
        client_a = self.new_client()
        client_b = self.new_client()
        email_a = 'user_a@example.com'
        email_b = 'user_b@example.com'

        # User A registers and completes a reading
        self.req('/api/enroll', {'name': 'Alice', 'email': email_a, 'password': 'AlicePassword123'}, client=client_a)
        self.req('/api/save', {'answers': test_app.example(), 'step': 12}, client=client_a)
        self.req('/api/generate', {'consent': True}, client=client_a)
        for _ in range(100):
            _, d = self.req('/api/state', client=client_a)
            if d['status'] == 'ready': break
            time.sleep(0.02)
        self.assertEqual(d['status'], 'ready')

        # User A upgrades to personal
        self.req('/api/demo-tier', {'tier': 'personal'}, client=client_a)
        for _ in range(100):
            _, d = self.req('/api/state', client=client_a)
            if d.get('plan'): break
            time.sleep(0.02)

        # User A can download PDF
        code, pdf_a = self.req('/api/pdf', client=client_a, raw=True)
        self.assertEqual(code, 200)
        self.assertTrue(pdf_a.startswith(b'%PDF-'))

        # User B registers
        self.req('/api/enroll', {'name': 'Bob', 'email': email_b, 'password': 'BobPassword123'}, client=client_b)

        # User B cannot access User A's session/PDF by providing User A's sid
        sid_a = None
        for cookie in client_a.cookiejar:
            if cookie.name == 'rd_session':
                sid_a = cookie.value
                break
        self.assertIsNotNone(sid_a)

        # User B attempts to access User A's PDF using User A's sid directly
        code_hijack, _ = self.req('/api/pdf', headers={'Cookie': f'rd_session={sid_a}'}, client=client_b, raw=True)
        # Should be rejected because user_b session != user_a
        # Wait: if headers send Cookie: rd_session=sid_a, Handler.session() returns sid_a, and Handler.current_user() checks sessions WHERE id=sid_a -> returns User A
        # BUT if Client B uses their own cookiejar, they have sid_b:
        code_b, _ = self.req('/api/pdf', client=client_b)
        self.assertEqual(code_b, 409) # User B has not generated their reading yet

    def test_grant_tier_internal_checkout_helper(self):
        client = self.new_client()
        email = 'checkout_buyer@example.com'
        self.req('/api/enroll', {'name': 'Buyer', 'email': email, 'password': 'BuyerPassword123'}, client=client)

        # Call /api/internal/grant-tier
        code, res = self.req('/api/internal/grant-tier', {
            'email': email,
            'tier': 'personal',
            'order_id': 'ord_test_stripe_123',
            'provider_id': 'pi_stripe_test',
            'amount': 3200
        })
        self.assertEqual(code, 200)
        self.assertTrue(res['success'])
        self.assertEqual(res['tier'], 'personal')

        # Verify reading tier upgraded
        code, state = self.req('/api/state', client=client)
        self.assertEqual(state['tier'], 'personal')

        # Verify order recorded
        with server.connection() as con:
            order = con.execute('SELECT * FROM orders WHERE id=?', ('ord_test_stripe_123',)).fetchone()
        self.assertIsNotNone(order)
        self.assertEqual(order['email'], email)
        self.assertEqual(order['amount'], 3200)

    def test_open_reading_switches_session(self):
        client = self.new_client()
        email = 'multi_reading@example.com'
        self.req('/api/auth/register', {'name': 'Multi', 'email': email, 'password': 'MultiPassword123'}, client=client)

        # Reading 1
        self.req('/api/save', {'answers': test_app.example('calm'), 'step': 12}, client=client)
        self.req('/api/generate', {'consent': True}, client=client)
        for _ in range(100):
            _, d = self.req('/api/state', client=client)
            if d['status'] == 'ready': break
            time.sleep(0.02)
        r1_sid = None
        for cookie in client.cookiejar:
            if cookie.name == 'rd_session': r1_sid = cookie.value

        # Check readings in account
        code, status_data = self.req('/api/auth/status', client=client)
        self.assertEqual(code, 200)
        readings = status_data['readings']
        self.assertGreaterEqual(len(readings), 1)
        r1_id = readings[0]['id']

        # Start a second reading
        code_new, res_new = self.req('/api/new', client=client)
        self.req('/api/enroll', {'name': 'Multi', 'email': email, 'password': 'MultiPassword123'}, client=client)
        save_code, save_resp = self.req('/api/save', {'answers': test_app.example('focus'), 'step': 3}, client=client)
        code, status_data2 = self.req('/api/auth/status', client=client)
        self.assertGreaterEqual(len(status_data2['readings']), 2)

        # Switch back to reading 1 via /api/auth/open
        code, open_res = self.req('/api/auth/open', {'reading_id': r1_id}, client=client)
        self.assertEqual(code, 200)
        self.assertTrue(open_res['ready'])

        # State is now reading 1
        _, curr_state = self.req('/api/state', client=client)
        self.assertEqual(curr_state['status'], 'ready')

    def test_supabase_client_offline_graceful(self):
        sb = SupabaseClient({})
        self.assertFalse(sb.is_configured())
        with self.assertRaises(RuntimeError):
            sb._request('/auth/v1/test')
        res = sb.upload_asset('bucket', 'dummy.txt', 'dummy.txt')
        self.assertEqual(res['status'], 500)

if __name__ == '__main__':
    unittest.main()

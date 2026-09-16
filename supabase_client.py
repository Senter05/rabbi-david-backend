"""Supabase REST Client for Rabbi David backend.
Uses standard library urllib to interact with Supabase GoTrue Auth, PostgREST, and Storage.
Seamlessly falls back or disables when environment variables are not set.
"""
import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error

def get_supabase_config(config=None):
    cfg = config or {}
    url = os.environ.get('SUPABASE_URL') or cfg.get('supabase_url', '')
    anon_key = os.environ.get('SUPABASE_ANON_KEY') or os.environ.get('SUPABASE_KEY') or cfg.get('supabase_anon_key') or cfg.get('supabase_key', '')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or cfg.get('supabase_service_role_key', '') or anon_key
    return {
        'url': url.rstrip('/'),
        'anon_key': anon_key,
        'service_key': service_key,
        'configured': bool(url and (anon_key or service_key))
    }

class SupabaseClient:
    def __init__(self, config=None):
        self.config = get_supabase_config(config)
        self.url = self.config['url']
        self.anon_key = self.config['anon_key']
        self.service_key = self.config['service_key']
        self.configured = self.config['configured']

    def is_configured(self):
        return self.configured

    def _request(self, path, method='GET', data=None, token=None, use_service_key=False, headers=None):
        if not self.configured:
            raise RuntimeError('Supabase is not configured')
        url = f"{self.url}{path}"
        req_headers = {
            'apikey': self.service_key if use_service_key else self.anon_key,
            'Content-Type': 'application/json'
        }
        auth_token = token or (self.service_key if use_service_key else self.anon_key)
        if auth_token:
            req_headers['Authorization'] = f"Bearer {auth_token}"
        if headers:
            req_headers.update(headers)

        payload = json.dumps(data).encode('utf-8') if data is not None else None
        req = urllib.request.Request(url, data=payload, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                body = resp.read()
                return {
                    'status': status,
                    'data': json.loads(body.decode('utf-8')) if body else None
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
            try:
                err_json = json.loads(err_body)
                msg = err_json.get('msg') or err_json.get('message') or err_json.get('error_description') or err_body
            except Exception:
                msg = err_body or f"HTTP {e.code}"
            return {
                'status': e.code,
                'error': msg,
                'data': None
            }
        except Exception as e:
            return {
                'status': 500,
                'error': str(e),
                'data': None
            }

    # Auth Methods
    def sign_up(self, email, password, name=''):
        """Registers a new user in Supabase Auth."""
        payload = {
            'email': email,
            'password': password,
            'data': {'name': name}
        }
        res = self._request('/auth/v1/signup', method='POST', data=payload)
        return res

    def sign_in(self, email, password):
        """Authenticates user with email and password via Supabase GoTrue."""
        payload = {
            'email': email,
            'password': password
        }
        res = self._request('/auth/v1/token?grant_type=password', method='POST', data=payload)
        return res

    def send_password_recovery(self, email, redirect_to=None):
        """Sends a password recovery email."""
        payload = {'email': email}
        if redirect_to:
            payload['redirect_to'] = redirect_to
        res = self._request('/auth/v1/recover', method='POST', data=payload)
        return res

    def update_password(self, access_token, new_password):
        """Updates user password using an authenticated access token."""
        payload = {'password': new_password}
        res = self._request('/auth/v1/user', method='PUT', data=payload, token=access_token)
        return res

    def get_user(self, access_token):
        """Gets user profile details from access token."""
        res = self._request('/auth/v1/user', method='GET', token=access_token)
        return res

    # Database / PostgREST Methods
    def upsert_session(self, sid, data, user_id=None, updated=None):
        if not self.configured: return {'status': 500, 'error': 'Not configured'}
        headers = {'Prefer': 'resolution=merge-duplicates'}
        payload = [{
            'id': sid,
            'user_id': user_id,
            'data': data if isinstance(data, (dict, list)) else json.loads(data),
            'updated': float(updated or time.time())
        }]
        return self._request('/rest/v1/sessions', method='POST', data=payload, use_service_key=True, headers=headers)

    def get_session(self, sid):
        if not self.configured: return None
        res = self._request(f"/rest/v1/sessions?id=eq.{urllib.parse.quote(sid)}&select=id,user_id,data,updated", method='GET', use_service_key=True)
        if res.get('status') == 200 and res.get('data') and len(res['data']) > 0:
            return res['data'][0]
        return None

    def get_user_sessions(self, user_id):
        if not self.configured or not user_id: return []
        res = self._request(f"/rest/v1/sessions?user_id=eq.{urllib.parse.quote(user_id)}&order=updated.desc", method='GET', use_service_key=True)
        if res.get('status') == 200 and res.get('data'):
            return res['data']
        return []

    def upsert_user(self, user_dict):
        if not self.configured or not user_dict: return {'status': 500, 'error': 'Not configured'}
        headers = {'Prefer': 'resolution=merge-duplicates'}
        payload = [{
            'id': user_dict['id'],
            'email': user_dict['email'],
            'password_hash': user_dict.get('password_hash'),
            'salt': user_dict.get('salt'),
            'name': user_dict.get('name', ''),
            'email_verified': int(user_dict.get('email_verified', 0)),
            'verification_token': user_dict.get('verification_token'),
            'created': float(user_dict.get('created', time.time())),
            'updated': float(user_dict.get('updated', time.time()))
        }]
        return self._request('/rest/v1/users', method='POST', data=payload, use_service_key=True, headers=headers)

    def get_user_by_email(self, email):
        if not self.configured or not email: return None
        res = self._request(f"/rest/v1/users?email=eq.{urllib.parse.quote(email.strip().lower())}&select=*", method='GET', use_service_key=True)
        if res.get('status') == 200 and res.get('data') and len(res['data']) > 0:
            return res['data'][0]
        return None

    def get_user_by_id(self, uid):
        if not self.configured or not uid: return None
        res = self._request(f"/rest/v1/users?id=eq.{urllib.parse.quote(uid)}&select=*", method='GET', use_service_key=True)
        if res.get('status') == 200 and res.get('data') and len(res['data']) > 0:
            return res['data'][0]
        return None

    def upsert_order(self, order_dict):
        if not self.configured or not order_dict: return {'status': 500, 'error': 'Not configured'}
        headers = {'Prefer': 'resolution=merge-duplicates'}
        payload = [{
            'id': order_dict['id'],
            'session_id': order_dict.get('session_id'),
            'email': order_dict['email'],
            'book_id': order_dict.get('book_id'),
            'amount': order_dict.get('amount', 0),
            'currency': order_dict.get('currency', 'usd'),
            'delivery_status': order_dict.get('delivery_status', 'pending'),
            'provider_id': order_dict.get('provider_id'),
            'user_id': order_dict.get('user_id'),
            'created': float(order_dict.get('created', time.time()))
        }]
        return self._request('/rest/v1/orders', method='POST', data=payload, use_service_key=True, headers=headers)

    def get_user_orders(self, user_id):
        if not self.configured or not user_id: return []
        res = self._request(f"/rest/v1/orders?user_id=eq.{urllib.parse.quote(user_id)}&order=created.desc", method='GET', use_service_key=True)
        if res.get('status') == 200 and res.get('data'):
            return res['data']
        return []

    # Storage Methods
    def upload_asset(self, bucket, file_path, dest_name, content_type='application/octet-stream', token=None):
        """Uploads a binary asset to a Supabase Storage bucket."""
        if not self.configured:
            return {'status': 500, 'error': 'Supabase not configured'}
        url = f"{self.url}/storage/v1/object/{bucket}/{dest_name}"
        headers = {
            'apikey': self.service_key,
            'Authorization': f"Bearer {self.service_key}",
            'Content-Type': content_type,
            'x-upsert': 'true'
        }
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                return {'status': resp.status, 'data': resp.read().decode('utf-8')}
        except Exception as e:
            return {'status': 500, 'error': str(e)}

    def download_asset(self, bucket, dest_name, local_path):
        """Downloads a binary asset from Supabase Storage and saves to local_path."""
        if not self.configured:
            return False
        headers = {
            'apikey': self.service_key,
            'Authorization': f"Bearer {self.service_key}"
        }
        for endpoint in [f"{self.url}/storage/v1/object/authenticated/{bucket}/{dest_name}", f"{self.url}/storage/v1/object/public/{bucket}/{dest_name}"]:
            try:
                req = urllib.request.Request(endpoint, headers=headers, method='GET')
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status == 200:
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        with open(local_path, 'wb') as f:
                            f.write(resp.read())
                        return True
            except Exception:
                continue
        return False

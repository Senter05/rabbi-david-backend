"""Supabase REST Client for Rabbi David backend.
Uses standard library urllib to interact with Supabase GoTrue Auth, PostgREST, and Storage.
Seamlessly falls back or disables when environment variables are not set.
"""
import os
import json
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
    def upsert_user_reading(self, reading_data, token=None):
        """Upserts a user reading record into user_readings table."""
        headers = {'Prefer': 'resolution=merge-duplicates'}
        return self._request(
            '/rest/v1/user_readings',
            method='POST',
            data=reading_data,
            token=token,
            use_service_key=True,
            headers=headers
        )

    def get_user_readings(self, user_id, token=None):
        """Fetches all readings for a specific user."""
        encoded_user_id = urllib.parse.quote(user_id)
        path = f"/rest/v1/user_readings?user_id=eq.{encoded_user_id}&order=updated_at.desc"
        return self._request(path, method='GET', token=token, use_service_key=True)

    # Storage Methods
    def upload_asset(self, bucket, file_path, dest_name, content_type='application/octet-stream', token=None):
        """Uploads a binary asset to a Supabase Storage bucket."""
        if not self.configured:
            return {'status': 500, 'error': 'Supabase not configured'}
        url = f"{self.url}/storage/v1/object/{bucket}/{dest_name}"
        headers = {
            'apikey': self.service_key,
            'Authorization': f"Bearer {self.service_key}",
            'Content-Type': content_type
        }
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                return {'status': resp.status, 'data': resp.read().decode('utf-8')}
        except Exception as e:
            return {'status': 500, 'error': str(e)}

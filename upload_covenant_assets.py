"""Upload the Covenant files to the PRIVATE Supabase bucket (covenant-private/covenant/) and check they are not public.

Usage: python upload_covenant_assets.py [--check-only]
Reads supabase_url / supabase_service_role_key from config.json or the SUPABASE_* environment variables.
"""
import json, sys, urllib.request, urllib.error
from pathlib import Path
import server
from supabase_client import get_supabase_config

ROOT = Path(__file__).resolve().parent


def main():
    cfg = {}
    if (ROOT / 'config.json').is_file(): cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    sb = get_supabase_config(cfg)
    if not sb['configured']: sys.exit('Supabase is not configured')
    head = {'apikey': sb['service_key'], 'Authorization': 'Bearer ' + sb['service_key']}
    with urllib.request.urlopen(urllib.request.Request(f"{sb['url']}/storage/v1/bucket/{server.COVENANT_BUCKET}", headers=head), timeout=20) as r:
        bucket = json.loads(r.read())
    if bucket.get('public'): sys.exit('Bucket is public: refusing to upload paid files')
    print('bucket', bucket.get('id'), 'public=', bucket.get('public'), 'file_size_limit=', bucket.get('file_size_limit'))
    for file_id, (local, storage_name, nice, mime) in server.covenant_file_table().items():
        src = next((f for f in local if f.is_file()), None)
        if not src: print('MISSING', file_id); continue
        if '--check-only' not in sys.argv:
            req = urllib.request.Request(f"{sb['url']}/storage/v1/object/{server.COVENANT_BUCKET}/{storage_name}", data=src.read_bytes(), method='POST',
                                         headers={**head, 'Content-Type': mime, 'x-upsert': 'true', 'Cache-Control': 'max-age=3600'})
            try:
                with urllib.request.urlopen(req, timeout=600) as r: r.read()
            except urllib.error.HTTPError as e:
                print('FAIL', storage_name, e.code, e.read()[:200]); continue
        # Public URL must NOT work; a signed URL must.
        try:
            urllib.request.urlopen(f"{sb['url']}/storage/v1/object/public/{server.COVENANT_BUCKET}/{storage_name}", timeout=20); public = True
        except urllib.error.HTTPError: public = False
        server.SUPABASE = server.SupabaseClient(cfg)
        signed = server.supabase_signed_url(storage_name, 60)
        size = None
        if signed:
            with urllib.request.urlopen(urllib.request.Request(signed, headers={'Range': 'bytes=0-0'}), timeout=30) as r:
                size = r.headers.get('Content-Range')
        print(('OK ' if signed and not public else 'CHECK ') + storage_name, src.stat().st_size, 'public=', public, 'signed=', size)


if __name__ == '__main__':
    main()

"""Local review application. Payments and public hosting are intentionally disabled."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from reading_access import reading_view
from input_validation import validate_contact_email,validate_written_answer
from pathlib import Path
import argparse,json,sqlite3,secrets,time,threading,urllib.parse,mimetypes,hashlib,re,copy,os
from operations import BoundedExecutor, CapacityError, origins, reserve, ProviderBudget
import providers
from contextlib import contextmanager
from content import VERSION,route,GOALS,PRACTICES,fallback_reading,draft_plan
from providers import generate_reading,generate_plan,generate_followup,generate_narration_script,submit_voice,poll_voice,download_audio,ProviderError
from documents import reading_pdf,plan_pdf
from source_library import SOURCE_BY_ID
from email.message import EmailMessage
from email import policy
from email.utils import parseaddr
import mail_delivery
from email_templates import add_html as add_email_html
from supabase_client import SupabaseClient

ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock();POOL=BoundedExecutor();STOP=threading.Event()
CONFIG={};DATA=None;DB=None;PORT=8100;AI_ENABLED=True;VOICE_ENABLED=False
EMAIL_RESOLVER=None
CATALOG=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
SUPABASE=None

@contextmanager
def connection():
    con=sqlite3.connect(DB,timeout=10);con.row_factory=sqlite3.Row
    try:
        with con:yield con
    finally:con.close()

def init(config,data,port=8100):
    global CONFIG,DATA,DB,PORT,SUPABASE
    CONFIG=config;origins(config,port);DATA=Path(data);DATA.mkdir(parents=True,exist_ok=True);(DATA/'audio').mkdir(exist_ok=True);DB=DATA/'state.sqlite';PORT=port
    SUPABASE=SupabaseClient(config)
    with connection() as con:
        con.executescript('''CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,data TEXT NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mail(id TEXT PRIMARY KEY,sid TEXT NOT NULL,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,due REAL NOT NULL,kind TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS access(token TEXT PRIMARY KEY,sid TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,sid TEXT,event TEXT,created REAL);
CREATE TABLE IF NOT EXISTS recovery_keys(token TEXT PRIMARY KEY,sid TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,session_id TEXT,email TEXT,book_id TEXT,amount INTEGER,currency TEXT,created REAL,delivery_status TEXT,provider_id TEXT,user_id TEXT);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,password_hash TEXT,salt TEXT,name TEXT,email_verified INTEGER DEFAULT 0,verification_token TEXT,created REAL,updated REAL);
CREATE TABLE IF NOT EXISTS password_resets(token TEXT PRIMARY KEY,user_id TEXT,expires REAL);''')
        columns={r[1] for r in con.execute('PRAGMA table_info(mail)')}
        if 'delivery_status' not in columns:con.execute("ALTER TABLE mail ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'local'")
        for field in ['delivery_error','provider_message_id']:
            if field not in columns:con.execute('ALTER TABLE mail ADD COLUMN '+field+' TEXT')
        con.execute("UPDATE mail SET delivery_status='needs_review' WHERE delivery_status='sending'")
        sess_cols={r[1] for r in con.execute('PRAGMA table_info(sessions)')}
        if 'user_id' not in sess_cols:con.execute('ALTER TABLE sessions ADD COLUMN user_id TEXT')
        ord_cols={r[1] for r in con.execute('PRAGMA table_info(orders)')}
        if 'user_id' not in ord_cols:con.execute('ALTER TABLE orders ADD COLUMN user_id TEXT')
        # A restarted worker must not pretend that an interrupted task completed.
        for row in con.execute('SELECT id,data FROM sessions').fetchall():
            d=json.loads(row['data']);d.pop('followup_pending',None)
            if d.get('plan_status')=='preparing':
                d.update(plan=draft_plan(d['answers']),plan_status='guided_alternative',plan_source='guided')
            if d.get('voice',{}).get('status')=='submitting':
                d['voice'].update(status='needs_review',error='The server restarted during submission. Check the existing provider task before retrying.')
            for field in ['voice','intro']:
                if d.get(field,{}).get('status')=='queued':d[field]['status']='not_requested'
            if d.get('intro',{}).get('status')=='submitting':
                d['intro'].update(status='needs_review',error='The server restarted during submission. Check the existing provider task before retrying.')
            if d.get('status')=='generating':
                d['status']='error';d['error']='Preparation was interrupted. Your answers are safe; please try again.'
            con.execute('UPDATE sessions SET data=? WHERE id=?',(json.dumps(d),row['id']))

    providers.REQUEST_GUARD=ProviderBudget(DB,CONFIG)

def blank():
    return dict(version=VERSION,started=False,answers={},step=0,revision=0,status='draft',tier='free',reading=None,plan=None,completed_days=[],email='',marketing=False,owned=[],voice={'status':'not_requested'},intro={'status':'not_requested'},created=time.time())

def valid_identity(name,email):
    if not isinstance(name,str) or not isinstance(email,str):raise ValueError('Please enter your first name and email address.')
    name=name.strip();email=email.strip().lower()
    if not 1<=len(name)<=60 or not any(c.isalpha() for c in name) or any(ord(c)<32 or c in '<>' for c in name):raise ValueError('Please enter your first name (up to 60 characters).')
    return name,validate_contact_email(email,resolver=EMAIL_RESOLVER)

def hash_password(password,salt=None):
    if not salt:salt=secrets.token_hex(16)
    try:h=hashlib.scrypt(password.encode('utf-8'),salt=salt.encode('utf-8'),n=16384,r=8,p=1).hex()
    except Exception:h=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt.encode('utf-8'),100000).hex()
    return salt,h

def verify_password(password,salt,password_hash):
    if not salt or not password_hash:return False
    try:h=hashlib.scrypt(password.encode('utf-8'),salt=salt.encode('utf-8'),n=16384,r=8,p=1).hex()
    except Exception:h=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt.encode('utf-8'),100000).hex()
    return secrets.compare_digest(h,password_hash)

def get_user_by_email(email):
    if not email:return None
    email=email.strip().lower()
    with connection() as con:
        r=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if r:return dict(r)
    if SUPABASE and SUPABASE.is_configured():
        try:
            remote=SUPABASE.get_user_by_email(email)
            if remote:
                with connection() as con:
                    con.execute('INSERT OR REPLACE INTO users(id,email,password_hash,salt,name,email_verified,verification_token,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
                                (remote['id'],remote['email'],remote.get('password_hash'),remote.get('salt'),remote.get('name',''),
                                 int(remote.get('email_verified',0)),remote.get('verification_token'),
                                 float(remote.get('created',time.time())),float(remote.get('updated',time.time()))))
                return remote
        except Exception as ex:print(f"[SUPABASE GET USER ERROR] {ex}",flush=True)
    return None

def get_user_by_id(uid):
    if not uid:return None
    with connection() as con:
        r=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if r:return dict(r)
    if SUPABASE and SUPABASE.is_configured():
        try:
            remote=SUPABASE.get_user_by_id(uid)
            if remote:
                with connection() as con:
                    con.execute('INSERT OR REPLACE INTO users(id,email,password_hash,salt,name,email_verified,verification_token,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
                                (remote['id'],remote['email'],remote.get('password_hash'),remote.get('salt'),remote.get('name',''),
                                 int(remote.get('email_verified',0)),remote.get('verification_token'),
                                 float(remote.get('created',time.time())),float(remote.get('updated',time.time()))))
                return remote
        except Exception as ex:print(f"[SUPABASE GET USER ERROR] {ex}",flush=True)
    return None

def create_or_get_user(email,password=None,name=''):
    email=email.strip().lower()
    u=get_user_by_email(email)
    if u:return u,False
    uid=secrets.token_urlsafe(16)
    salt,pw_hash=hash_password(password) if password else ('','')
    v_token=secrets.token_urlsafe(32)
    now=time.time()
    user_dict={'id':uid,'email':email,'password_hash':pw_hash,'salt':salt,'name':name,'email_verified':0,'verification_token':v_token,'created':now,'updated':now}
    with connection() as con:
        con.execute('INSERT INTO users(id,email,password_hash,salt,name,email_verified,verification_token,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
                    (uid,email,pw_hash,salt,name,0,v_token,now,now))
    if SUPABASE and SUPABASE.is_configured():
        try:POOL.submit(lambda: SUPABASE.upsert_user(user_dict))
        except Exception as ex:print(f"[SUPABASE USER SYNC ERROR] {ex}",flush=True)
    return get_user_by_id(uid),True

def safe_user(u):
    if not u:return None
    return {'id':u['id'],'email':u['email'],'name':u.get('name',''),'email_verified':bool(u.get('email_verified')),'created':u.get('created')}

def link_user_sessions(user_id,email,active_sid=None):
    # Knowing an email is not proof of ownership of its earlier readings/orders.
    # Only attach the session whose bearer cookie the authenticated caller holds.
    if not user_id or not email or not active_sid:return
    with connection() as con:
        row=con.execute('SELECT data,user_id FROM sessions WHERE id=?',(active_sid,)).fetchone()
        if not row:return
        d=json.loads(row['data'])
        owner=row['user_id'] or d.get('user_id')
        if owner and owner!=user_id:raise ValueError('Sign out before changing accounts.')
        d['user_id']=user_id
        if not d.get('email'):d['email']=email.strip().lower()
        now=time.time()
        con.execute('UPDATE sessions SET user_id=?,data=?,updated=? WHERE id=?',(user_id,json.dumps(d),now,active_sid))
    if SUPABASE and SUPABASE.is_configured():
        try:POOL.submit(lambda: SUPABASE.upsert_session(active_sid,d,user_id,now))
        except Exception as ex:print(f"[SUPABASE LINK SYNC ERROR] {ex}",flush=True)


def get_user_readings_list(user_id):
    if not user_id:return []
    if SUPABASE and SUPABASE.is_configured():
        try:
            remote_sessions=SUPABASE.get_user_sessions(user_id)
            if remote_sessions:
                with connection() as con:
                    for rs in remote_sessions:
                        con.execute('INSERT OR REPLACE INTO sessions(id,data,updated,user_id) VALUES(?,?,?,?)',
                                    (rs['id'],json.dumps(rs['data']) if isinstance(rs['data'],dict) else str(rs['data']),
                                     float(rs.get('updated',time.time())),user_id))
        except Exception as ex:print(f"[SUPABASE SESSIONS SYNC ERROR] {ex}",flush=True)
    readings=[]
    with connection() as con:
        rows=con.execute('SELECT id,data,updated FROM sessions WHERE user_id=? ORDER BY updated DESC',(user_id,)).fetchall()
        for r in rows:
            d=json.loads(r['data'])
            if not d.get('started') and not d.get('reading') and len(d.get('answers',{}))<=1:continue
            goal=d.get('answers',{}).get('goal','')
            title='Your Personal Reading'
            reading_obj=d.get('reading') or {}
            if reading_obj.get('title'):title=reading_obj['title']
            elif goal:title=f"Reading: {goal.replace('_',' ').capitalize()}"
            readings.append({
                'id':r['id'],
                'title':title,
                'status':d.get('status','draft'),
                'tier':d.get('tier','free'),
                'updated':r['updated'],
                'has_audio':bool(d.get('audio_file') and d.get('voice',{}).get('status')=='ready'),
                'audio_url':f"/api/audio?id={r['id']}" if (d.get('audio_file') and d.get('voice',{}).get('status')=='ready') else None,
                'has_plan':bool(d.get('plan') and d.get('tier')=='personal'),
                'plan_pdf_url':f"/api/plan-pdf?id={r['id']}" if (d.get('plan') and d.get('tier')=='personal') else None,
                'has_pdf':bool(d.get('status')=='ready'),
                'pdf_url':f"/api/pdf?id={r['id']}",
                'step':d.get('step',0),
                'completed_days':d.get('completed_days',[])
            })
    return readings

def send_auth_mail(recipient,subject,body,kind='auth'):
    mid=secrets.token_hex(16)
    with connection() as con:
        con.execute('INSERT INTO mail(id,sid,recipient,subject,body,due,kind,created,delivery_status) VALUES(?,?,?,?,?,?,?,?,?)',
                    (mid,'auth',recipient,subject,body,time.time(),kind,time.time(),'pending' if mail_configured() else 'local'))

def new_session():
    sid=secrets.token_urlsafe(32)
    with connection() as con:con.execute('INSERT INTO sessions(id,data,updated) VALUES(?,?,?)',(sid,json.dumps(blank()),time.time()))
    return sid

def get(sid):
    with connection() as con:r=con.execute('SELECT data FROM sessions WHERE id=?',(sid,)).fetchone()
    if r:return json.loads(r['data'])
    if SUPABASE and SUPABASE.is_configured():
        try:
            remote=SUPABASE.get_session(sid)
            if remote and remote.get('data'):
                d=remote['data']
                uid=remote.get('user_id')
                upd=float(remote.get('updated',time.time()))
                d_str=json.dumps(d) if isinstance(d,dict) else str(d)
                with connection() as con:
                    con.execute('INSERT OR REPLACE INTO sessions(id,data,updated,user_id) VALUES(?,?,?,?)',(sid,d_str,upd,uid))
                return d if isinstance(d,dict) else json.loads(d_str)
        except Exception as ex:print(f"[SUPABASE GET SESSION ERROR] {ex}",flush=True)
    return None

def update(sid,fn):
    with LOCK:
        with connection() as con:
            r=con.execute('SELECT data,user_id FROM sessions WHERE id=?',(sid,)).fetchone()
            if not r and SUPABASE and SUPABASE.is_configured():
                try:
                    remote=SUPABASE.get_session(sid)
                    if remote and remote.get('data'):
                        d_rem=remote['data']
                        uid_rem=remote.get('user_id')
                        upd_rem=float(remote.get('updated',time.time()))
                        con.execute('INSERT OR REPLACE INTO sessions(id,data,updated,user_id) VALUES(?,?,?,?)',
                                    (sid,json.dumps(d_rem) if isinstance(d_rem,dict) else str(d_rem),upd_rem,uid_rem))
                        r=con.execute('SELECT data,user_id FROM sessions WHERE id=?',(sid,)).fetchone()
                except Exception as ex:print(f"[SUPABASE UPDATE RESTORE ERROR] {ex}",flush=True)
            if not r:raise ValueError('Session not found')
            d=json.loads(r['data']);fn(d)
            uid=d.get('user_id') or r['user_id']
            now=time.time()
            con.execute('UPDATE sessions SET data=?,updated=?,user_id=? WHERE id=?',(json.dumps(d),now,uid,sid))
    if SUPABASE and SUPABASE.is_configured():
        try:POOL.submit(lambda: SUPABASE.upsert_session(sid,d,uid,now))
        except Exception as ex:print(f"[SUPABASE SESSION SYNC ERROR] {ex}",flush=True)
    return d

def event(sid,name):
    with connection() as con:con.execute('INSERT INTO events(sid,event,created) VALUES(?,?,?)',(sid,name,time.time()))

def mail(sid,kind,subject,body,due=None):
    d=get(sid)
    if not d or not d.get('email'):return
    mid=hashlib.sha256(f'{sid}:{d["revision"]}:{kind}'.encode()).hexdigest()
    with connection() as con:
        con.execute('INSERT OR IGNORE INTO mail(id,sid,recipient,subject,body,due,kind,created,delivery_status) VALUES(?,?,?,?,?,?,?,?,?)',(mid,sid,d['email'],subject,body,due or time.time(),kind,time.time(),'pending' if mail_configured() else 'local'))

def public_origin():
    return (os.environ.get('PUBLIC_ORIGIN') or CONFIG.get('public_origin') or ('https://rabbidavid.org' if os.environ.get('PRODUCTION')=='1' or os.environ.get('RENDER') or os.environ.get('RENDER_EXTERNAL_HOSTNAME') else f'http://127.0.0.1:{PORT}')).rstrip('/')

def recovery_mail(sid):
    d=get(sid); token=secrets.token_urlsafe(32)
    with connection() as con:
        con.execute('DELETE FROM access WHERE expires<?',(time.time(),))
        con.execute('INSERT INTO access VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),sid,time.time()+900))
    # Queue only newly requested mail when SMTP is configured; existing local previews stay local.
    mid=secrets.token_hex(16)
    with connection() as con:
        con.execute('INSERT INTO mail(id,sid,recipient,subject,body,due,kind,created,delivery_status) VALUES(?,?,?,?,?,?,?,?,?)',(mid,sid,d['email'],'Rabbi David | Your sign-in link',f'Shalom,\n\nWelcome back. Use the button below to return to your reading.\n\n{public_origin()}/access?token={token}\n\nThis private link works once and expires in 15 minutes. If you did not request it, ignore this email.\n\nWith warmth,\nThe Rabbi David Team',time.time(),'access',time.time(),'pending' if mail_configured() else 'local'))

def sync_delivery(sid):
    d=get(sid)
    if not d or d.get('status')!='ready':return
    name=d['answers'].get('name','')
    access_note=('Your opening reflection is ready. It connects your answers with a Jewish teaching and a practical first step.'
                 if d['tier']=='free' else 'Your complete reading is ready. Explore the teaching, consider what fits your situation, and choose one practical step.')
    body=f"Shalom {name},\n\n{access_note}\n\n{public_origin()}/account.html\n\nSign in with the email address you used for your reading.\n\nWith warmth,\nThe Rabbi David Team"
    subject='Rabbi David | Your opening reflection is ready' if d['tier']=='free' else 'Rabbi David | Your complete reading is ready'
    mail(sid,'reading_'+d['tier'],subject,body)
    if d['marketing']:
        for days,subject,body in [
            (1,'Rabbi David | One small step today','A useful teaching becomes more meaningful when you try it. Revisit your reading and choose one small action that fits today.'),
            (5,'Rabbi David | Take a moment to reflect','What felt useful? What would you adjust? Return to your reading with what you have learned from trying it.')]:
            mail(sid,'followup_'+str(days),subject,f'Shalom {name},\n\n{body}\n\n{public_origin()}/account.html\n\nYou can turn off these optional reminders in your reading under Email preferences.\n\nWith warmth,\nThe Rabbi David Team',time.time()+days*86400)


def prepare_plan_delivery(sid):
    """Prepare the actual attachment locally; no external delivery is claimed."""
    d=get(sid)
    if d['tier']!='personal' or not d.get('plan'):return
    pdf=plan_pdf(d)
    mid=hashlib.sha256(f'{sid}:{d["revision"]}:plan'.encode()).hexdigest()
    message=EmailMessage()
    message['To']=d['email']
    message['Subject']='Rabbi David | Your personal 14-day plan and audio are ready'
    message.set_content(f"Shalom {d['answers']['name']},\n\nYour personal 14-day plan is attached as a PDF.\n\nYour personal audio reading is also ready to listen to directly in your account:\n\n{public_origin()}/result.html\n\nOr sign in anytime here:\n\n{public_origin()}/account.html\n\nMay peace and blessing rest upon the work of your hands.\n\nWith warmth,\nRabbi David & Team")
    add_email_html(message,'plan',public_origin())
    message.add_attachment(pdf,maintype='application',subtype='pdf',filename='your-personal-14-day-plan.pdf')
    directory=DATA/'outbox';directory.mkdir(exist_ok=True)
    target=directory/(mid+'.eml');temporary=directory/(mid+'.tmp')
    temporary.write_bytes(message.as_bytes());temporary.replace(target)
    mail(sid,'plan',message['Subject'],message.get_body(preferencelist=('plain',)).get_content())

EBOOK_DELIVERY = {
    'rituals': {
        'title': 'The 7 Jewish Money Rituals',
        'files': ['The-7-Jewish-Money-Rituals.pdf'],
        'url': 'https://rabbidavid.org/download/rituals.html'
    },
    'legacy': {
        'title': 'Generational Wealth: The Torah Method',
        'files': ['Generational-Wealth-The-Torah-Method.pdf'],
        'url': 'https://rabbidavid.org/download/generational-wealth.html'
    },
    'complete': {
        'title': "The Complete Rabbi's Wealth System",
        'files': [
            'The-Rabbis-Morning-Wealth-Blessing.pdf',
            'Generational-Wealth-The-Torah-Method.pdf',
            'The-7-Jewish-Money-Rituals.pdf',
            'The-Complete-Rabbis-Wealth-System.pdf'
        ],
        'url': 'https://rabbidavid.org/download/complete.html'
    },
    'ceo': {
        'title': 'The Torah CEO Code',
        'files': ['The-Torah-CEO-Code.pdf'],
        'url': 'https://rabbidavid.org/download/torah-ceo-code.html'
    },
    'morning': {
        'title': "The Rabbi's Morning Wealth Blessing",
        'files': ['The-Rabbis-Morning-Wealth-Blessing.pdf'],
        'url': 'https://rabbidavid.org/download/morning-blessing.html'
    }
}

def deliver_ebook(order_id, email, name, book_id, session_id='', amount=0, currency='usd'):
    if not book_id or book_id not in EBOOK_DELIVERY:
        amount_map = {3200: 'rituals', 7700: 'legacy', 15000: 'complete', 4600: 'ceo', 2700: 'morning'}
        book_id = amount_map.get(amount, 'complete' if amount >= 15000 else 'rituals')
    info = EBOOK_DELIVERY[book_id]
    message = EmailMessage()
    message['To'] = email
    sender = CONFIG.get('mail_from') or 'Rabbi David <david@rabbidavid.org>'
    message['From'] = sender
    message['Subject'] = f"Rabbi David | Your book: {info['title']}"
    body = (
        f"Shalom {name},\n\nThank you for your order. Your digital book, {info['title']}, is ready.\n\n"
        f"Download your materials here:\n\n{info['url']}\n\n"
        "Any attached PDFs are also yours to keep. Need help? Contact sentercompanyls@gmail.com.\n\n"
        "With warmth,\nThe Rabbi David Team\nSenter Company LLC"
    )
    message.set_content(body)
    add_email_html(message,'ebook','https://rabbidavid.org')
    ebooks_dir = ROOT / 'ebooks'
    if not ebooks_dir.is_dir():
        ebooks_dir = ROOT / 'public' / 'pdf'
    for filename in info['files']:
        pdf_path = ebooks_dir / filename
        if pdf_path.is_file():
            message.add_attachment(
                pdf_path.read_bytes(),
                maintype='application',
                subtype='pdf',
                filename=filename
            )
    provider_id = None
    status = 'pending'
    if mail_configured():
        try:
            provider_id = mail_delivery.send(CONFIG, message, order_id)
            status = 'sent'
        except Exception as e:
            status = 'failed'
            print(f"[EBOOK DELIVERY ERROR] order={order_id} error={e}", flush=True)
    else:
        status = 'local_preview'
    with connection() as con:
        u = get_user_by_email(email)
        uid = u['id'] if u else None
        con.execute(
            "INSERT OR REPLACE INTO orders(id,session_id,email,book_id,amount,currency,created,delivery_status,provider_id,user_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (order_id, session_id, email, book_id, amount, currency, time.time(), status, provider_id, uid)
        )
    if SUPABASE and SUPABASE.is_configured():
        try:POOL.submit(lambda: SUPABASE.upsert_order({'id':order_id,'session_id':session_id,'email':email,'book_id':book_id,'amount':amount,'currency':currency,'delivery_status':status,'provider_id':provider_id,'user_id':uid,'created':time.time()}))
        except Exception as ex:print(f"[SUPABASE EBOOK ORDER SYNC ERROR] {ex}",flush=True)
    return {'ok': True, 'status': status, 'provider_id': provider_id, 'book_id': book_id}

def apply_tier_purchase(order_id, session_id, buyer_email, name, raw_tier, amount=0, currency='usd', metadata=None):
    metadata = metadata or {}
    effective_tier = 'personal' if raw_tier in ('personal', 'upgrade') else 'reading'
    target_sid = metadata.get('session_id') or session_id or ''
    target_uid = metadata.get('user_id') or ''
    registered_email = metadata.get('registered_email') or metadata.get('email') or ''
    resolved_sid = None
    if target_sid:
        with connection() as con:
            row = con.execute("SELECT id FROM sessions WHERE id=?", (target_sid,)).fetchone()
            if row: resolved_sid = row['id']
    resolved_uid = target_uid
    if not resolved_uid and registered_email:
        u = get_user_by_email(registered_email)
        if u: resolved_uid = u['id']
    if not resolved_uid and buyer_email:
        u = get_user_by_email(buyer_email)
        if u: resolved_uid = u['id']
    if not resolved_sid and resolved_uid:
        with connection() as con:
            row = con.execute("SELECT id FROM sessions WHERE user_id=? ORDER BY updated DESC LIMIT 1", (resolved_uid,)).fetchone()
            if row: resolved_sid = row['id']
    if resolved_sid:
        def set_tier(d):
            d['tier'] = effective_tier
            d['paid'] = True
            if buyer_email: d['billing_email'] = buyer_email
            if resolved_uid and not d.get('user_id'): d['user_id'] = resolved_uid
            if effective_tier == 'personal':
                d['auto_audio'] = True
                if not d.get('plan'):
                    d['plan_status'] = 'preparing'
        d_updated = update(resolved_sid, set_tier)
        if effective_tier == 'personal':
            if not d_updated.get('plan'):
                schedule(plan_job, resolved_sid, d_updated['revision'])
            else:
                try: prepare_plan_delivery(resolved_sid)
                except Exception as ex: print(f"[PLAN DELIVERY ON PURCHASE ERROR] {ex}", flush=True)
                schedule(voice_job, resolved_sid)
    status = 'delivered'
    with connection() as con:
        con.execute(
            "INSERT OR REPLACE INTO orders(id,session_id,email,book_id,amount,currency,created,delivery_status,provider_id,user_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (order_id, resolved_sid or target_sid, buyer_email or registered_email, 'tier:'+effective_tier, amount, currency, time.time(), status, session_id, resolved_uid)
        )
    if SUPABASE and SUPABASE.is_configured():
        try:
            POOL.submit(lambda: SUPABASE.upsert_order({
                'id': order_id,
                'session_id': resolved_sid or target_sid,
                'email': buyer_email or registered_email,
                'book_id': 'tier:'+effective_tier,
                'amount': amount,
                'currency': currency,
                'delivery_status': status,
                'provider_id': session_id,
                'user_id': resolved_uid,
                'created': time.time()
            }))
        except Exception as ex: print(f"[SUPABASE TIER ORDER SYNC ERROR] {ex}", flush=True)
    return {'ok': True, 'tier': effective_tier, 'session_id': resolved_sid, 'user_id': resolved_uid}

def valid_answers(raw,complete=False,followup=None,unchanged=None):
    if not isinstance(raw,dict):raise ValueError('Please check your answers')
    a={}
    if 'name' in raw:
        if not isinstance(raw['name'],str) or len(raw['name'])>60:raise ValueError('Please use a name of up to 60 characters')
        a['name']=raw['name'].strip()
    for q in route(raw)+([followup] if followup else []):
        v=raw.get(q['id'])
        if v is None or v=='':
            if complete and not q.get('optional'):raise ValueError('Please answer the remaining questions')
            continue
        if not isinstance(v,str):raise ValueError('Please check your selection')
        if q['type']=='choice' and v not in {o['value'] for o in q['options']}:raise ValueError('Please choose one of the available answers')
        if len(v)>q.get('maxLength',600):raise ValueError('Please shorten your answer')
        if q['type']!='choice' and not (unchanged is not None and unchanged.get(q['id'])==v):
            try:v=validate_written_answer(v)
            except ValueError as error:raise ValueError(q['title']+' — '+str(error)) from None
        a[q['id']]=v.strip()
    return a

def safe_state(d):
    s=copy.deepcopy(d);s['questions']=route(d['answers'])+([d['followup']] if d.get('followup') else []);s['preview_mode']=True;s['voice_configured']=bool(CONFIG.get('ai33_key') and CONFIG.get('ai33_voice_id'));s['voice_generation_enabled']=VOICE_ENABLED
    s['free_testing']=CONFIG.get('free_testing') is True
    s['answer_issues']=[]
    for q in s['questions']:
        if q['type']!='choice':
            try:validate_written_answer(d['answers'].get(q['id'],''))
            except ValueError as error:s['answer_issues'].append(dict(id=q['id'],message=str(error)))
    if s.get('reading'):
        s['reading'],s['preview']=reading_view(s['reading'],s['tier'])
        for section in s['reading'].get('sections',[]):
            source=SOURCE_BY_ID.get(section.get('source_id'))
            if source:section['source']={k:source[k] for k in ('title','url')}
    for day in s.get('plan') or []:
        source=SOURCE_BY_ID.get(day.get('source_id'))
        if source:day['source']={k:source[k] for k in ('title','url')}
    if s['tier']!='personal':s['plan']=None
    s['voice']={k:v for k,v in s['voice'].items() if k in ['status','progress','error','credit_cost']}
    is_voice_local=(DATA/'audio'/f'{s.get("audio_file", "none")}').is_file() if s.get('audio_file') else False
    s['voice']['available']=is_voice_local or bool(SUPABASE and SUPABASE.is_configured() and s.get('audio_file') and s.get('voice',{}).get('status')=='ready')
    intro=d.get('intro',{'status':'not_requested'})
    s['intro']={k:v for k,v in intro.items() if k in ['status','error','progress']}
    is_intro_local=bool(d.get('intro_file') and (DATA/'audio'/d['intro_file']).is_file())
    s['intro']['available']=is_intro_local or bool(SUPABASE and SUPABASE.is_configured() and d.get('intro_file') and intro.get('status')=='ready')
    s.pop('intro_file',None)
    s.pop('audio_file',None);s.pop('usage',None)
    s.pop('reading_diagnostic',None);s.pop('plan_diagnostic',None)
    s['email_delivery_enabled']=mail_configured()
    if d['status']=='ready':
        owned_items=set(d['owned'])
        for owned_book in CATALOG:
            if owned_book['id'] in d['owned']:
                owned_items.update(item['id'] for item in owned_book.get('includedBooks',[]))
        candidates=[b for b in CATALOG if b.get('active',True) and b['id'] not in owned_items]
        primary=GOALS[d['answers']['goal']]['book']
        chosen=next((b for b in candidates if b['id']==primary),None)
        s['recommendation']=dict(book=chosen,reason=f"You chose {GOALS[d['answers']['goal']]['theme']} as your priority. This existing book explores a related theme; it is optional and is not included in the reading.") if chosen else None
    return s

def generate_job(sid,revision,local=False):
    d=get(sid);a=d['answers'];base=fallback_reading(a)
    if d.get('followup'):a={**a,'personal_question':d['followup']['title']}
    try:
        if not local and AI_ENABLED:
            def progress(completed,total):
                def record(x):
                    if x['revision']==revision:x.update(generation_progress=dict(completed=completed,total=total))
                update(sid,record)
            reading,usage=generate_reading(CONFIG,a,base,progress=progress);source='ai'
        else:reading,usage,source=base,{},'guided'
        def done(x):
            if x['revision']!=revision:return
            x.update(reading=reading,status='ready',error=None,source=source,usage=usage,reading_version=3 if source=='ai' else 0)
        current=update(sid,done);event(sid,'reading_ready');sync_delivery(sid)
        if current['revision']==revision and current['tier']=='personal' and not current.get('plan') and (source=='ai' or not current.get('auto_audio')):
            update(sid,lambda x:x.update(plan_status='preparing'));schedule(plan_job,sid,revision)
    except Exception as error:
        diagnostic=str(error) if isinstance(error,ProviderError) else f"{type(error).__name__}: {str(error)}"
        print(f"[GENERATION ERROR] reference={hashlib.sha256(sid.encode()).hexdigest()[:12]} revision={revision} type={type(error).__name__}", flush=True)
        if CONFIG.get('graceful_fallback', True):
            reading, usage, source = base, {}, 'guided_fallback'
            def fallback_done(x):
                if x['revision']!=revision:return
                x.update(reading=reading,status='ready',error=None,source=source,usage=usage,reading_version=0,reading_diagnostic={'reason':diagnostic,'at':time.time()})
            current=update(sid,fallback_done);event(sid,'reading_ready');sync_delivery(sid)
            if current['revision']==revision and current['tier']=='personal' and not current.get('plan'):
                update(sid,lambda x:x.update(plan_status='preparing'));schedule(plan_job,sid,revision)
        else:
            def fail(x):
                if x['revision']==revision:
                    x.update(
                        status='error',
                        reading_diagnostic={'reason':diagnostic,'at':time.time()},
                    error='Your reading could not be completed. Your answers are saved. Please try again or contact support.'
                    )
            update(sid,fail)

def start_voice(sid,kind='personal'):
    d=get(sid)
    if d['voice'].get('task_id') or d['voice']['status'] in ['submitting','ready','needs_review']:return
    name=d['answers'].get('name') or 'my friend'
    if kind=='welcome':script=f'{name}, your answers are saved. Your personal reading is being prepared. You can stay here, or return to your personal space later. We will show you when it is ready. Thank you for taking this time for yourself.'
    else:
        try:
            script=generate_narration_script(CONFIG, d['answers'], d.get('reading') or {}, d.get('plan') or [])
        except Exception:
            script=f"{name}, welcome to your personal reading. "+d['reading']['summary']+' '+d['reading']['insight']+' '
            script+=' '.join(item['interpretation'] for item in d['reading'].get('evidence',[]))+' '
            step=d['reading'].get('first_step')
            if step:script+=' '.join(step[k] for k in ('action','why','reflection'))+' '
            def spoken_excerpt(text):
                paragraph=text.split('\n\n')[0]
                sentences=re.split(r'(?<=[.!?])\s+',paragraph)
                selected=[]
                for sentence in sentences:
                    if selected and len((' '.join(selected+[sentence])).split())>150:break
                    selected.append(sentence)
                return ' '.join(selected)
            script+=' '.join(spoken_excerpt(s['text']) for s in d['reading']['sections'])
            plan_action=d.get('plan',[{}])[0].get('action','') if d.get('plan') else ''
            script+=' For the next fourteen days, your written plan invites you to take one small step at a time. '+plan_action+' At the end of each week, notice what felt useful and what you would change. There is no need to rush. You can return to this reading whenever you wish.'
    update(sid,lambda x:x.update(voice={'status':'submitting','script':script,'kind':kind}))
    try:
        task=submit_voice(CONFIG,script,'rabbi-reading-'+secrets.token_hex(6))
        update(sid,lambda x:x['voice'].update(status='processing',task_id=task,submitted_at=time.time()))
    except Exception:
        update(sid,lambda x:x['voice'].update(status='needs_review',error='Audio submission needs a check before trying again. Your written reading is available.'))

def plan_job(sid,revision):
    d=get(sid);base=draft_plan(d['answers'])
    try:
        answers={**d['answers'],'personal_question':d['followup']['title']} if d.get('followup') else d['answers']
        plan=generate_plan(CONFIG,answers,base) if AI_ENABLED else base
        # A plan is only ready when its complete, readable PDF can be produced.
        plan_pdf({**d,'plan':plan})
        def ready(x):
            if x['revision']==revision:x.update(plan=plan,plan_status='ready',plan_source='ai' if AI_ENABLED else 'guided',plan_version=2 if AI_ENABLED else 1)
        update(sid,ready)
    except Exception as error:
        def fallback(x):
            if x['revision']==revision:x.update(plan=x.get('plan') or base,plan_status='guided_alternative',plan_source='guided',plan_diagnostic=str(error) if isinstance(error,ProviderError) else type(error).__name__)
        update(sid,fallback)
    current=get(sid)
    if current['revision']==revision and current.get('plan'):
        try:prepare_plan_delivery(sid)
        except Exception:update(sid,lambda x:x.update(plan_delivery_error='The email attachment could not be prepared. Your plan remains available on the website.'))
    if current['revision']==revision and current.get('auto_audio'):queue_preview_audio(sid)

def queue_preview_audio(sid):
    if not VOICE_ENABLED:return
    with LOCK:
        d=get(sid)
        if d['status']!='ready' or d.get('source')!='ai' or not d.get('plan'):return
        valid_answers(d['answers'],True,followup=d.get('followup'))
        if d['voice']['status']=='not_requested' and not d['voice'].get('task_id'):
            update(sid,lambda x:x['voice'].update(status='queued'))
            schedule(start_voice,sid)

def enable_free_preview(sid):
    if CONFIG.get('free_testing') is not True:raise ValueError('Free testing is not enabled')
    with LOCK:
        d=get(sid)
        if d['status']!='ready' or d.get('source')!='ai':raise ValueError('Prepare your personal reading first')
        valid_answers(d['answers'],True,followup=d.get('followup'))
        update(sid,lambda x:x.update(tier='personal',auto_audio=True))
        if not d.get('plan') and d.get('plan_status')!='preparing':
            update(sid,lambda x:x.update(plan_status='preparing'))
            schedule(plan_job,sid,d['revision'])
        if VOICE_ENABLED and d.get('intro',{}).get('status','not_requested')=='not_requested':
            update(sid,lambda x:x.update(intro={'status':'queued'}))
            schedule(intro_job,sid)
    queue_preview_audio(sid)
    sync_delivery(sid)
    return get(sid)

def intro_job(sid):
    d=get(sid);name=d['answers'].get('name') or 'my friend'
    script=f'Shalom, {name}. Welcome to your personal reading. Begin with the idea that speaks to you, then choose one small step to try. You can listen and reflect at your own pace. Thank you for making this moment for yourself.'
    update(sid,lambda x:x.update(intro={'status':'submitting','script':script}))
    try:
        task=submit_voice(CONFIG,script,'rabbi-welcome-'+secrets.token_hex(6))
        update(sid,lambda x:x['intro'].update(status='processing',task_id=task,submitted_at=time.time()))
    except Exception:update(sid,lambda x:x['intro'].update(status='needs_review',error='The spoken welcome needs a provider check. Your reading and plan remain available.'))

def schedule(fn,sid,*args):
    try:
        d=get(sid)
        if not d:raise ValueError('Session no longer available')
        identity=hashlib.sha256((d.get('email') or sid).encode()).hexdigest()
        reserve(DB,'jobs:'+identity,int(CONFIG.get('max_jobs_per_day',20)))
        return POOL.submit(fn,sid,*args)
    except CapacityError:
        def reset(x):
            if fn==generate_job:x.update(status='error',error='Preparation is busy. Please try again shortly.')
            elif fn==plan_job:x.update(plan_status='guided_alternative',plan=x.get('plan') or draft_plan(x['answers']),plan_source='guided')
            elif fn==start_voice:x.update(voice={'status':'not_requested'})
            elif fn==intro_job:x.update(intro={'status':'not_requested'})
        update(sid,reset)
        raise

def purge_session(sid):
    with LOCK:
        d=get(sid)
        if not d:return
        if d.get('status')=='generating' or d.get('plan_status')=='preparing' or d.get('followup_pending') or any(d.get(k,{}).get('status') in ['queued','submitting','processing','download_pending'] for k in ['voice','intro']):
            raise ValueError('Please wait for preparation to finish before deleting this reading.')
        with connection() as con:
            ids=[r['id'] for r in con.execute('SELECT id FROM mail WHERE sid=?',(sid,))]
            for table in ['mail','access','events','recovery_keys']:con.execute(f'DELETE FROM {table} WHERE sid=?',(sid,))
            con.execute('DELETE FROM sessions WHERE id=?',(sid,))
        for name in [d.get('audio_file'),d.get('intro_file')]:
            if name and Path(name).name==name:(DATA/'audio'/name).unlink(missing_ok=True)
        for mid in ids:(DATA/'outbox'/(mid+'.eml')).unlink(missing_ok=True)

def expire_sessions():
    # Runs periodically; active generations are left for the next pass.
    cutoff=time.time()-int(CONFIG.get('retention_days',90))*86400
    with connection() as con:
        ids=[r['id'] for r in con.execute('SELECT id FROM sessions WHERE updated<?',(cutoff,))]
        con.execute('DELETE FROM access WHERE expires<?',(time.time(),))
        con.execute('DELETE FROM recovery_keys WHERE expires<?',(time.time(),))
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='quotas'").fetchone():
            con.execute("DELETE FROM quotas WHERE (bucket LIKE 'requests:%' AND window<?) OR (bucket NOT LIKE 'requests:%' AND window<?)",(int(time.time()//60)-2,int(time.time()//86400)-2))
    for sid in ids:
        try:purge_session(sid)
        except ValueError:pass

def process_voice(sid,field):
    d=get(sid)
    if not d:return
    v=d.get(field,{})
    if v.get('status') not in ['processing','download_pending']:return
    now=time.time();started=v.get('submitted_at',now)
    if not v.get('submitted_at'):update(sid,lambda x:x[field].update(submitted_at=now))
    if now-started>int(CONFIG.get('voice_timeout_seconds',1800)):
        update(sid,lambda x:x[field].update(status='needs_review',error='Audio is taking longer than expected. Contact support with your reading open. The existing recording will be checked before any retry.'))
        event(sid,'voice_timeout:'+field);return
    if now<v.get('next_poll_at',0):return
    try:
        task=poll_voice(CONFIG,v['task_id'])
        if task.get('status')=='error':
            update(sid,lambda x:x[field].update(status='needs_review',error='The recording needs a support check. Your written reading is available.'));event(sid,'voice_provider_error:'+field)
        elif task.get('status')=='done':
            name=hashlib.sha256(sid.encode()).hexdigest()+('-welcome.mp3' if field=='intro' else '.mp3')
            update(sid,lambda x:x[field].update(status='download_pending'))
            download_audio(task['metadata']['audio_url'],DATA/'audio'/name)
            if SUPABASE and SUPABASE.is_configured():
                try:POOL.submit(lambda: SUPABASE.upload_asset('user-assets', DATA/'audio'/name, f"audio/{name}", 'audio/mpeg'))
                except Exception as ex:print(f"[SUPABASE AUDIO UPLOAD ERROR] {ex}",flush=True)
            def done(x):
                x['intro_file' if field=='intro' else 'audio_file']=name
                x[field].update(status='ready',progress=100,credit_cost=task.get('credit_cost'),poll_errors=0)
            update(sid,done)
        else:update(sid,lambda x:x[field].update(progress=task.get('progress',0),poll_errors=0,next_poll_at=now+8))
    except Exception:
        count=v.get('poll_errors',0)+1
        update(sid,lambda x:x[field].update(poll_errors=count,next_poll_at=now+min(300,8*2**min(count,6))))
        event(sid,'voice_poll_error:'+field)

def mail_configured():return mail_delivery.transport(CONFIG)!='local'

def dispatch_mail_once():
    if not mail_configured():return
    from email.parser import BytesParser
    with LOCK:
        with connection() as con:
            row=con.execute("SELECT * FROM mail WHERE due<=? AND delivery_status='pending' ORDER BY created LIMIT 1",(time.time(),)).fetchone()
            if not row:return
            con.execute("UPDATE mail SET delivery_status='sending' WHERE id=?",(row['id'],))
    try:
        attachment=DATA/'outbox'/(row['id']+'.eml')
        if row['kind']=='plan' and not attachment.is_file():
            raise mail_delivery.MailDeliveryError('plan_attachment_missing')
        message=BytesParser(policy=policy.default).parsebytes(attachment.read_bytes()) if row['kind']=='plan' else EmailMessage()
        if not message.get('To'):
            message['To']=row['recipient'];message['Subject']=row['subject'];message.set_content(row['body'])
        add_email_html(message,row['kind'],public_origin())
        # Use the current recipient even when a saved MIME attachment is older.
        if message.get('To'):message.replace_header('To',row['recipient'])
        message['From']=CONFIG['mail_from'];message['Message-ID']='<'+row['id']+'@'+parseaddr(CONFIG['mail_from'])[1].split('@')[-1]+'>'
        provider_id=mail_delivery.send(CONFIG,message,row['id'])
        status='sent';error=None
    except Exception as exc:
        status='needs_review';provider_id=None
        error=str(exc) if isinstance(exc,mail_delivery.MailDeliveryError) else 'mail_preparation_failed'
        print(f"[MAIL ERROR] reference={row['id'][:8]} reason={error}",flush=True)
    with connection() as con:con.execute('UPDATE mail SET delivery_status=?,delivery_error=?,provider_message_id=? WHERE id=?',(status,error,provider_id,row['id']))


def poll_voices():
    maintenance=0
    while not STOP.wait(8):
        with connection() as con:rows=con.execute('SELECT id FROM sessions').fetchall()
        for row in rows:
            process_voice(row['id'],'intro');process_voice(row['id'],'voice')
        dispatch_mail_once()
        if time.time()>maintenance:expire_sessions();maintenance=time.time()+3600


class Handler(BaseHTTPRequestHandler):
    server_version='RabbiDavid'
    def log_message(self,*args):pass
    def headers_common(self,mime,cache='no-store'):
        self.send_header('Content-Type',mime);self.send_header('Cache-Control',cache)
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        origin=self.headers.get('Origin')
        if origin in origins(CONFIG,PORT):
            self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Access-Control-Allow-Credentials','true');self.send_header('Vary','Origin')
        if getattr(self,'new_cookie',None):
            secure='; Secure' if public_origin().startswith('https://') else ''
            self.send_header('Set-Cookie','rd_session='+self.new_cookie+'; HttpOnly; Path=/; Max-Age=2592000; SameSite=Lax'+secure)
        if getattr(self,'clear_cookie',False):self.send_header('Set-Cookie','rd_session=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax')
    def send(self,status=200,obj=None,body=None,mime='application/json',headers=None):
        if body is None:body=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status);self.headers_common(mime)
        self.send_header('Content-Length',str(len(body)))
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
    def send_file(self,file,mime=None,private=False):
        size=file.stat().st_size;etag='"'+str(file.stat().st_mtime_ns)+'-'+str(size)+'"'
        cache='no-store' if private else ('no-cache' if file.suffix=='.html' else 'public, max-age=3600')
        if not private and self.headers.get('If-None-Match')==etag:
            self.send_response(304);self.headers_common(mime or mimetypes.guess_type(str(file))[0] or 'application/octet-stream',cache);self.send_header('ETag',etag);self.end_headers();return
        start,end,status=0,size-1,200
        requested=self.headers.get('Range')
        if requested:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
            if not match or not any(match.groups()):return self.send(416,body=b'',headers={'Content-Range':f'bytes */{size}'})
            first,last=match.groups()
            if first:start=int(first);end=min(int(last),size-1) if last else size-1
            else:start=max(0,size-int(last))
            if start>end or start>=size:return self.send(416,body=b'',headers={'Content-Range':f'bytes */{size}'})
            status=206
        self.send_response(status);self.headers_common(mime or mimetypes.guess_type(str(file))[0] or 'application/octet-stream',cache)
        self.send_header('Content-Length',str(max(0,end-start+1)));self.send_header('Accept-Ranges','bytes')
        if not private:self.send_header('ETag',etag)
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with file.open('rb') as stream:
                stream.seek(start);remaining=end-start+1
                while remaining>0:
                    chunk=stream.read(min(65536,remaining))
                    if not chunk:break
                    self.wfile.write(chunk);remaining-=len(chunk)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
    def session(self):
        cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
        sid=cookie['rd_session'].value if 'rd_session' in cookie else ''
        if not re.fullmatch(r'[A-Za-z0-9_-]{40,50}',sid) or not get(sid):sid=new_session();self.new_cookie=sid
        return sid
    def current_user(self):
        sid=self.session()
        with connection() as con:
            r=con.execute('SELECT user_id FROM sessions WHERE id=?',(sid,)).fetchone()
            if r and r['user_id']:return get_user_by_id(r['user_id'])
        return None
    def allowed_host(self):
        allowed={urllib.parse.urlsplit(value).netloc for value in origins(CONFIG,PORT)}
        backend=os.environ.get('RENDER_EXTERNAL_HOSTNAME','')
        if backend:allowed.add(backend)
        return self.headers.get('Host','') in allowed
    def allowed_origin(self):
        return not self.headers.get('Origin') or self.headers.get('Origin') in origins(CONFIG,PORT)
    def do_OPTIONS(self):
        if not self.allowed_host() or not self.allowed_origin():return self.send(403,{'error':'Request not allowed'})
        return self.send(204,body=b'',headers={'Access-Control-Allow-Methods':'GET, POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type, X-Requested-With'})
    def do_GET(self):
        if not self.allowed_host() or not self.allowed_origin():return self.send(403,{'error':'This preview is available only on authorized hosts.'})
        u=urllib.parse.urlparse(self.path);path=u.path;sid=self.session() if path.startswith('/api/') or path=='/access' else None
        try:
            if path=='/api/auth/status':
                curr=self.current_user()
                readings=get_user_readings_list(curr['id']) if curr else []
                return self.send(obj={'enabled':True,'user':safe_user(curr),'readings':readings})
            if path=='/api/auth/verify-email':
                token=urllib.parse.parse_qs(u.query).get('token',[''])[0]
                if not token:return self.send(400,{'error':'Missing verification token'})
                with connection() as con:
                    r=con.execute('SELECT id FROM users WHERE verification_token=?',(token,)).fetchone()
                    if not r:return self.send(400,{'error':'Invalid verification token'})
                    con.execute('UPDATE users SET email_verified=1,updated=? WHERE id=?',(time.time(),r['id']))
                return self.send(obj={'message':'Email successfully verified.'})
            if path=='/api/state':return self.send(obj=safe_state(get(sid)))
            if path=='/api/catalog':return self.send(obj=[b for b in CATALOG if b.get('active',True)])
            if path=='/api/practices':return self.send(obj=PRACTICES)
            if path=='/api/config':return self.send(obj=dict(version=VERSION,model=CONFIG.get('openrouter_model',''),mode='preview',payments=False,email=mail_delivery.transport(CONFIG),support='email' if mail_configured() and CONFIG.get('support_email') else 'local',ai=AI_ENABLED,voice=VOICE_ENABLED,free_testing=CONFIG.get('free_testing') is True))
            if path=='/api/export':
                return self.send(obj=safe_state(get(sid)),headers={'Content-Disposition':'attachment; filename="my-reading-data.json"'})
            if path=='/api/inbox':
                with connection() as con:rows=con.execute('SELECT id,recipient,subject,body,due,kind,delivery_status,delivery_error,provider_message_id FROM mail WHERE sid=? ORDER BY created DESC',(sid,)).fetchall()
                items=[dict(r) for r in rows]
                for item in items:
                    if item['kind']=='plan' and (DATA/'outbox'/(item['id']+'.eml')).is_file():item['attachment_preview']='/api/plan-email?id='+item['id']
                return self.send(obj=items)
            if path=='/api/plan-pdf':
                target_id=urllib.parse.parse_qs(u.query).get('id',[''])[0] or sid
                d=get(target_id);curr=self.current_user()
                is_owner=(target_id==sid) or (curr and d.get('user_id')==curr['id']) or (curr and curr.get('email') and d.get('email')==curr.get('email'))
                if not is_owner:return self.send(403,{'error':'Unauthorized access to this reading'})
                if curr and not d.get('user_id') and d.get('email')==curr.get('email'):
                    update(target_id,lambda x:x.update(user_id=curr['id']))
                if d['tier']!='personal':return self.send(403,{'error':'Your personal plan is required'})
                if d['status']!='ready' or not d.get('plan'):return self.send(409,{'error':'Your plan is still being prepared'})
                return self.send(body=plan_pdf(d),mime='application/pdf',headers={'Content-Disposition':'inline; filename="your-personal-14-day-plan.pdf"'})
            if path=='/api/plan-email':
                mid=urllib.parse.parse_qs(u.query).get('id',[''])[0]
                with connection() as con:owned=con.execute("SELECT id FROM mail WHERE id=? AND sid=? AND kind='plan'",(mid,sid)).fetchone()
                if not owned:return self.send(404,{'error':'Email preview not found'})
                file=DATA/'outbox'/(owned['id']+'.eml')
                if not file.is_file():return self.send(404,{'error':'Email preview is not ready'})
                return self.send(body=file.read_bytes(),mime='message/rfc822',headers={'Content-Disposition':'attachment; filename="your-plan-email.eml"'})
            if path=='/api/pdf':
                target_id=urllib.parse.parse_qs(u.query).get('id',[''])[0] or sid
                d=get(target_id);curr=self.current_user()
                is_owner=(target_id==sid) or (curr and d.get('user_id')==curr['id']) or (curr and curr.get('email') and d.get('email')==curr.get('email'))
                if not is_owner:return self.send(403,{'error':'Unauthorized access to this reading'})
                if curr and not d.get('user_id') and d.get('email')==curr.get('email'):
                    update(target_id,lambda x:x.update(user_id=curr['id']))
                if d['status']!='ready':return self.send(409,{'error':'Your reading is not ready yet'})
                return self.send(body=reading_pdf(d),mime='application/pdf',headers={'Content-Disposition':'attachment; filename="your-rabbi-david-reading.pdf"'})
            if path=='/api/audio':
                target_id=urllib.parse.parse_qs(u.query).get('id',[''])[0] or sid
                d=get(target_id);curr=self.current_user()
                is_owner=(target_id==sid) or (curr and d.get('user_id')==curr['id']) or (curr and curr.get('email') and d.get('email')==curr.get('email'))
                if not is_owner:return self.send(403,{'error':'Unauthorized access to this reading'})
                if curr and not d.get('user_id') and d.get('email')==curr.get('email'):
                    update(target_id,lambda x:x.update(user_id=curr['id']))
                if not d.get('audio_file') or d.get('voice',{}).get('status')!='ready':return self.send(404,{'error':'Audio is not ready'})
                target=DATA/'audio'/d['audio_file']
                if not target.is_file() and SUPABASE and SUPABASE.is_configured():
                    SUPABASE.download_asset('user-assets', f"audio/{d['audio_file']}", target)
                if not target.is_file():return self.send(404,{'error':'Audio file could not be retrieved'})
                return self.send_file(target,mime='audio/mpeg',private=True)
            if path=='/api/welcome':
                d=get(sid);curr=self.current_user()
                if d.get('user_id') and (not curr or curr['id']!=d['user_id']):return self.send(403,{'error':'Unauthorized access to this reading'})
                if not d.get('intro_file') or d.get('intro',{}).get('status')!='ready':return self.send(404,{'error':'Welcome is not ready'})
                target=DATA/'audio'/d['intro_file']
                if not target.is_file() and SUPABASE and SUPABASE.is_configured():
                    SUPABASE.download_asset('user-assets', f"audio/{d['intro_file']}", target)
                if not target.is_file():return self.send(404,{'error':'Welcome file could not be retrieved'})
                return self.send_file(target,mime='audio/mpeg',private=True)
            if path=='/api/transcript':
                target_id=urllib.parse.parse_qs(u.query).get('id',[''])[0] or sid
                d=get(target_id);curr=self.current_user()
                if d.get('user_id') and (not curr or curr['id']!=d['user_id']):return self.send(403,{'error':'Unauthorized access to this reading'})
                if not d.get('user_id') and target_id!=sid:return self.send(403,{'error':'Unauthorized access to this reading'})
                if d['tier']!='personal':return self.send(403,{'error':'Personal plan required'})
                return self.send(body=d['voice'].get('script','Audio has not been requested.').encode(),mime='text/plain; charset=utf-8')
            if path=='/access':
                token=urllib.parse.parse_qs(u.query).get('token',[''])[0]
                with LOCK:
                    with connection() as con:
                        hashed=hashlib.sha256(token.encode()).hexdigest();r=con.execute('SELECT sid FROM access WHERE token=? AND expires>?',(hashed,time.time())).fetchone()
                        con.execute('DELETE FROM access WHERE token=?',(hashed,))
                if not r:return self.send(400,body=b'Your link has expired or was already used. Return to the website to request another.',mime='text/plain')
                self.new_cookie=r['sid'];return self.send(303,body=b'',headers={'Location':'/result.html'})
            if path=='/api/download-verify':
                return self.handle_download_verify(u)
            if path=='/api/checkout-verify':
                return self.handle_checkout_verify(u)
            if path=='/api/new':
                self.new_cookie=new_session()
                curr=self.current_user()
                if curr:
                    def init_user_session(x):
                        x.update(user_id=curr['id'],email=curr['email'],started=True)
                        x['answers']['name']=curr.get('name') or 'Friend'
                    update(self.new_cookie,init_user_session)
                    link_user_sessions(curr['id'],curr['email'],self.new_cookie)
                return self.send(obj=safe_state(get(self.new_cookie)))
            if path.startswith('/api/'):return self.send(404,{'error':'Not found'})
            if path=='/':path='/index.html'
            f=(ROOT/'public'/urllib.parse.unquote(path.lstrip('/'))).resolve()
            if not f.is_relative_to((ROOT/'public').resolve()) or not f.is_file():return self.send(404,{'error':'Not found'})
            return self.send_file(f)
        except Exception:return self.send(500,{'error':'Something could not be loaded. Please try again.'})
    def handle_stripe_webhook(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<=0 or length>500000:return self.send(400,{'error':'Invalid payload size'})
            raw=self.rfile.read(length)
            event=json.loads(raw)
            if event.get('type')=='checkout.session.completed':
                session=event.get('data',{}).get('object',{})
                session_id=session.get('id','')
                customer_details=session.get('customer_details') or {}
                email=customer_details.get('email') or session.get('customer_email') or ''
                name=customer_details.get('name') or 'Valued Reader'
                metadata=session.get('metadata') or {}
                book_id=metadata.get('book_id','')
                tier=metadata.get('tier','')
                amount=session.get('amount_total',0)
                currency=session.get('currency','usd')
                order_id='ord_'+(session_id if session_id else hashlib.sha256(raw).hexdigest()[:16])
                if book_id and email:
                    deliver_ebook(order_id,email,name,book_id,session_id=session_id,amount=amount,currency=currency)
                elif tier:
                    apply_tier_purchase(order_id,session_id,email,name,tier,amount=amount,currency=currency,metadata=metadata)
            return self.send(200,{'received':True})
        except Exception as e:
            print(f"[STRIPE WEBHOOK ERROR] {e}",flush=True)
            return self.send(400,{'error':'Webhook processing error'})
    def handle_download_verify(self,u):
        qs=urllib.parse.parse_qs(u.query)
        session_id=qs.get('session_id',[''])[0]
        if not session_id:return self.send(400,{'error':'Missing session_id'})
        with connection() as con:
            order=con.execute("SELECT * FROM orders WHERE session_id=?",(session_id,)).fetchone()
        if order:
            return self.send(200,{'verified':True,'email':order['email'],'book_id':order['book_id'],'delivery_status':order['delivery_status']})
        return self.send(200,{'verified':False,'status':'processing'})
    def handle_checkout_verify(self,u):
        qs=urllib.parse.parse_qs(u.query)
        checkout_id=qs.get('checkout_session_id',[''])[0]
        sid=self.session()
        d=get(sid)
        if d.get('tier') in ('reading','personal'):
            return self.send(200,{'unlocked':True,'tier':d['tier']})
        if not checkout_id:
            return self.send(200,{'unlocked':False,'tier':d.get('tier','free')})
        with connection() as con:
            order=con.execute("SELECT * FROM orders WHERE provider_id=?",(checkout_id,)).fetchone()
        if order:
            tier=order['book_id'].replace('tier:','') if order['book_id'].startswith('tier:') else 'personal'
            update(sid,lambda x:x.update(tier=tier,paid=True))
            return self.send(200,{'unlocked':True,'tier':tier})
        stripe_key=os.environ.get('STRIPE_SECRET_KEY') or CONFIG.get('stripe_secret_key')
        if stripe_key and re.fullmatch(r'cs_[A-Za-z0-9_]+',checkout_id):
            try:
                req=urllib.request.Request(f'https://api.stripe.com/v1/checkout/sessions/{checkout_id}',headers={'Authorization':f'Bearer {stripe_key}'})
                with urllib.request.urlopen(req,timeout=15) as r:
                    cs=json.loads(r.read())
                if cs.get('payment_status')=='paid':
                    meta=cs.get('metadata') or {}
                    raw_tier=meta.get('tier','personal')
                    cust=cs.get('customer_details') or {}
                    buyer_email=cust.get('email') or cs.get('customer_email') or ''
                    order_id='ord_'+checkout_id
                    apply_tier_purchase(order_id,checkout_id,buyer_email,cust.get('name') or '',raw_tier,amount=cs.get('amount_total',0),currency=cs.get('currency','usd'),metadata=meta)
                    return self.send(200,{'unlocked':True,'tier':'personal' if raw_tier in ('personal','upgrade') else 'reading'})
            except Exception as ex:
                print(f"[CHECKOUT VERIFY ERROR] {ex}",flush=True)
        return self.send(200,{'unlocked':False,'status':'pending'})
    def do_POST(self):
        path=urllib.parse.urlsplit(self.path).path
        if path=='/api/stripe-webhook':
            return self.handle_stripe_webhook()
        if not self.allowed_host() or self.headers.get('X-Requested-With')!='RabbiDavid':return self.send(403,{'error':'Request not allowed'})
        if not self.allowed_origin():return self.send(403,{'error':'Request not allowed'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>20000:return self.send(413,{'error':'Please shorten your message'})
            reserve(DB,'requests:'+hashlib.sha256(self.client_address[0].encode()).hexdigest(),int(CONFIG.get('max_requests_per_minute',120)),60)
            body=json.loads(self.rfile.read(length));sid=self.session();d=get(sid);path=urllib.parse.urlsplit(self.path).path
            if not isinstance(body,dict):raise ValueError('Please check the request')
            if path in ['/api/save','/api/generate','/api/followup','/api/demo-tier','/api/voice','/api/intro'] and not d.get('started'):return self.send(403,{'error':'Enter your first name and email before beginning the test.'})
            if path=='/api/enroll':
                name,email=valid_identity(body.get('name'),body.get('email'))
                if d.get('started'):return self.send(obj=safe_state(d))
                password=body.get('password')
                if not isinstance(password,str) or not 8<=len(password)<=128:
                    raise ValueError('Please choose a password with at least 8 characters.')
                u=get_user_by_email(email)
                if u:
                    if not u.get('password_hash') or not verify_password(password,u['salt'],u['password_hash']):
                        raise ValueError('An account with this email already exists. Please sign in with your password or use password recovery.')
                else:
                    u,created=create_or_get_user(email,password,name)
                    if not created and not verify_password(password,u['salt'],u['password_hash']):
                        raise ValueError('Please sign in with your password or use password recovery.')
                    if created and SUPABASE.is_configured():
                        try:SUPABASE.sign_up(email,password,name)
                        except Exception:print('[SUPABASE SIGNUP ERROR] Account synchronization failed',flush=True)
                    if created and mail_configured():
                        send_auth_mail(email,'Rabbi David | Welcome to your account',f"Shalom {name},\n\nYour account is ready. It gives you one place to return to your readings.\n\n{public_origin()}/account.html\n\nUse your email address and password to sign in.\n\nWith warmth,\nThe Rabbi David Team",'welcome')
                user_id=u['id']
                if d.get('user_id') and d['user_id']!=user_id:
                    sid=new_session();self.new_cookie=sid;d=get(sid)
                def enroll(x):
                    if x.get('started'):return
                    x.update(started=True,email=email,marketing=body.get('marketing') is True,enrolled_at=time.time())
                    if user_id:x['user_id']=user_id
                    x['answers']['name']=name
                d=update(sid,enroll);event(sid,'test_started');sync_delivery(sid)
                if user_id:link_user_sessions(user_id,email,sid)
            elif path=='/api/save':
                if d.get('reading') or d['status']=='ready':raise ValueError('This test is complete. Start a new test to change your answers.')
                if d['status']=='generating':raise ValueError('Please wait for your reading before editing')
                if d.get('voice',{}).get('status') in ['queued','submitting','processing','download_pending']:raise ValueError('Please wait for the audio to finish before editing these answers. You can start a separate reflection instead.')
                if d.get('intro',{}).get('status') in ['queued','submitting','processing','download_pending']:raise ValueError('Please wait for the welcome to finish before editing these answers.')
                a=valid_answers(body.get('answers',{}),followup=d.get('followup'),unchanged=d['answers']);step=body.get('step',0)
                valid_identity(a.get('name'),d['email'])
                if type(step)!=int or not 0<=step<=15:raise ValueError('Invalid step')
                def save(x):
                    if x.get('reading') or x['status']=='ready':raise ValueError('This test is complete. Start a new test to change your answers.')
                    if x['status']=='generating':raise ValueError('Please wait for your reading before editing')
                    base=lambda values:{k:v for k,v in values.items() if k not in ['name','personal_detail']}
                    if x.get('followup') and base(a)!=base(x['answers']):x.pop('followup',None);a.pop('personal_detail',None)
                    x.update(answers=a,step=min(step,len(route(a))+(1 if x.get('followup') else 0)))
                    if x['status']=='error':x.update(status='draft',error=None,generation_progress=None)
                d=update(sid,save)
            elif path=='/api/followup':
                valid_answers(d['answers'],True)
                if d['status']!='draft' or body.get('consent') is not True:raise ValueError('Please confirm use of your answers for this optional question')
                with LOCK:
                    d=get(sid)
                    if d.get('followup'):return self.send(obj=safe_state(d))
                    if d.get('followup_pending'):return self.send(409,{'error':'Your optional question is already being prepared. Please wait.'})
                    update(sid,lambda x:x.update(followup_pending=True))
                try:
                    if not AI_ENABLED:raise ProviderError('Offline')
                    title=generate_followup(CONFIG,d['answers']);source='ai'
                except Exception:
                    title='What would one ordinary day look like if it better reflected the priority you chose?';source='guided'
                q=dict(id='personal_detail',title=title,hint='An optional follow-up based on your answers. Share only what feels comfortable.',type='text',optional=True,maxLength=600)
                def followup_ready(x):
                    x.pop('followup_pending',None)
                    if x['answers']==d['answers'] and x['status']=='draft':x.update(followup=q,followup_source=source,step=len(route(x['answers'])))
                d=update(sid,followup_ready)
            elif path=='/api/generate':
                if d['status']=='generating':return self.send(obj=safe_state(d))
                refreshing=body.get('refresh') is True and (d.get('source')!='ai' or d.get('reading_version',0)<3)
                if d['status']=='ready' and not refreshing:
                    valid_answers(d['answers'],True,followup=d.get('followup'))
                    return self.send(obj=safe_state(d))
                if refreshing and any(d.get(k,{}).get('status') in ['queued','submitting','processing','download_pending'] for k in ('voice','intro')):raise ValueError('Please wait for your audio to finish before updating the reading')
                valid_answers(d['answers'],True,followup=d.get('followup'))
                if body.get('consent') is not True:raise ValueError('Please confirm that we may use your answers to prepare your reading')
                with LOCK:
                    current=get(sid)
                    refreshing=body.get('refresh') is True and (current.get('source')!='ai' or current.get('reading_version',0)<3)
                    if current['status']=='generating' or (current['status']=='ready' and not refreshing):return self.send(obj=safe_state(current))
                    valid_answers(current['answers'],True,followup=current.get('followup'))
                    def begin(x):
                        x.update(status='generating',revision=x['revision']+1,error=None,consent_at=time.time(),generation_started_at=time.time(),reading_diagnostic=None,generation_progress=dict(completed=0,total=5))
                        if CONFIG.get('free_testing') is True:x.update(tier='personal',auto_audio=True)
                        if refreshing:
                            x.update(plan=None,plan_status=None,completed_days=[],voice={'status':'not_requested'},intro={'status':'not_requested'})
                            x.pop('audio_file',None);x.pop('intro_file',None)
                    d=update(sid,begin)
                    event(sid,'test_complete');schedule(generate_job,sid,d['revision'],body.get('guided') is True)
            elif path=='/api/contact':
                _,email=valid_identity(d['answers'].get('name'),body.get('email',''))
                marketing=body.get('marketing') is True
                d=update(sid,lambda x:x.update(email=email,marketing=marketing))
                # Local outbox messages have not been dispatched. A corrected
                # address must apply to existing delivery previews as well.
                with connection() as con:con.execute("UPDATE mail SET recipient=? WHERE sid=? AND kind!='support' AND delivery_status IN ('local','pending')",(email,sid))
                if not marketing:
                    with connection() as con:con.execute("DELETE FROM mail WHERE sid=? AND kind LIKE 'followup_%'",(sid,))
                sync_delivery(sid)
                if d['tier']=='personal' and d.get('plan'):
                    try:prepare_plan_delivery(sid)
                    except Exception:pass
            elif path=='/api/free-preview':
                d=enable_free_preview(sid)
            elif path=='/api/demo-tier':
                if d['status']!='ready':raise ValueError('Complete your reading first')
                valid_answers(d['answers'],True,followup=d.get('followup'))
                if AI_ENABLED and d.get('source')!='ai':raise ValueError('Prepare your personal reading first. The provisional reflection cannot be upgraded.')
                tier=body.get('tier')
                if tier not in ['reading','personal']:raise ValueError('Choose a reading option')
                if tier==d['tier']:return self.send(obj=safe_state(d))
                if d['tier']=='personal' and tier=='reading':raise ValueError('Your personal plan already includes the full reading')
                def upgrade(x):
                    x['tier']=tier
                    if tier=='personal' and not x.get('plan'):x['plan_status']='preparing'
                with LOCK:
                    current=get(sid)
                    if tier==current['tier']:return self.send(obj=safe_state(current))
                    if current['tier']=='personal':raise ValueError('Your personal plan already includes the full reading')
                    d=update(sid,upgrade);sync_delivery(sid);event(sid,'preview_'+tier)
                    if tier=='personal' and d.get('plan_status')=='preparing':schedule(plan_job,sid,d['revision'])
            elif path=='/api/create-checkout-session':
                tier=body.get('tier')
                if tier not in ['reading','personal','upgrade']:raise ValueError('Invalid tier')
                stripe_key=os.environ.get('STRIPE_SECRET_KEY') or CONFIG.get('stripe_secret_key')
                if not stripe_key:raise ValueError('Stripe is not configured')
                amounts={'reading':100,'personal':100,'upgrade':100}
                names={'reading':'The Complete Reading — Rabbi David','personal':'The Personal Path (Reading, 14-Day Plan & Audio) — Rabbi David','upgrade':'Personal Path Upgrade (14-Day Plan & Audio) — Rabbi David'}
                unit_amount=amounts.get(tier,100)
                prod_name=names.get(tier,names['personal'])
                success_url=f"{public_origin()}/result.html?checkout_session_id={{CHECKOUT_SESSION_ID}}&paid=true"
                cancel_url=f"{public_origin()}/result.html"
                user_email=d.get('email') or (self.current_user() or {}).get('email') or ''
                user_id=d.get('user_id') or (self.current_user() or {}).get('id') or ''
                params={
                    'payment_method_types[]':'card',
                    'mode':'payment',
                    'success_url':success_url,
                    'cancel_url':cancel_url,
                    'line_items[0][price_data][currency]':'usd',
                    'line_items[0][price_data][unit_amount]':str(unit_amount),
                    'line_items[0][price_data][product_data][name]':prod_name,
                    'line_items[0][quantity]':'1',
                    'metadata[session_id]':sid,
                    'metadata[user_id]':user_id,
                    'metadata[registered_email]':user_email,
                    'metadata[tier]':tier
                }
                if user_email:params['customer_email']=user_email
                data=urllib.parse.urlencode(params).encode('utf-8')
                req=urllib.request.Request('https://api.stripe.com/v1/checkout/sessions',data=data,headers={'Authorization':f'Bearer {stripe_key}'})
                with urllib.request.urlopen(req,timeout=15) as r:
                    cs_data=json.loads(r.read())
                return self.send(200,{'ok':True,'checkout_url':cs_data.get('url'),'session_id':cs_data.get('id')})
            elif path=='/api/plan-retry':
                if body.get('consent') is not True:raise ValueError('Please confirm preparation of your detailed plan.')
                if not AI_ENABLED:raise ValueError('Personal plan generation is not connected.')
                with LOCK:
                    current=get(sid)
                    if current['tier']!='personal' or current['status']!='ready':raise ValueError('Complete your personal reading first.')
                    if current.get('plan_status')=='preparing' or (current.get('plan_source')=='ai' and current.get('plan_version',0)>=2):return self.send(obj=safe_state(current))
                    if current.get('completed_days'):raise ValueError('Keep the plan you have started, or begin a new test for a new plan.')
                    valid_answers(current['answers'],True,followup=current.get('followup'))
                    d=update(sid,lambda x:x.update(plan_status='preparing',plan_delivery_error=None))
                    schedule(plan_job,sid,d['revision'])
            elif path=='/api/voice':
                if not VOICE_ENABLED:raise ValueError('Voice generation is disabled in this preview. The recording integration is prepared.')
                if d['tier']!='personal' or d['status']!='ready' or not d.get('plan'):raise ValueError('Please wait for your personal plan first')
                with LOCK:
                    current=get(sid)
                    if not current['voice'].get('task_id') and current['voice']['status']=='not_requested':
                        update(sid,lambda x:x['voice'].update(status='queued'));schedule(start_voice,sid,'personal')
                d=get(sid)
            elif path=='/api/intro':
                if not VOICE_ENABLED or d['tier']!='personal':raise ValueError('Spoken welcome is not available')
                with LOCK:
                    if get(sid).get('intro',{}).get('status','not_requested')=='not_requested':
                        update(sid,lambda x:x.update(intro={'status':'queued'}));schedule(intro_job,sid)
                d=get(sid)
            elif path=='/api/days':
                if d['tier']!='personal':raise ValueError('Open the personal plan first')
                days=body.get('days')
                if not isinstance(days,list) or any(type(v)!=int or not 1<=v<=14 for v in days):raise ValueError('Invalid days')
                d=update(sid,lambda x:x.update(completed_days=sorted(set(days))))
            elif path=='/api/owned':
                owned=body.get('owned',[])
                if not isinstance(owned,list) or any(v not in {b['id'] for b in CATALOG} for v in owned):raise ValueError('Invalid book selection')
                d=update(sid,lambda x:x.update(owned=list(set(owned))))
            elif path=='/api/recovery-key':
                if not d.get('started'):raise ValueError('Start your reading first.')
                token=secrets.token_urlsafe(32)
                with connection() as con:
                    con.execute('DELETE FROM recovery_keys WHERE sid=?',(sid,))
                    con.execute('INSERT INTO recovery_keys VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),sid,time.time()+90*86400))
                return self.send(obj={'key':token,'message':'Keep this private recovery key. It replaces any earlier key and expires in 90 days.'})
            elif path=='/api/recover-key':
                token=body.get('key','')
                if not isinstance(token,str) or len(token)>100:raise ValueError('Invalid recovery key.')
                with connection() as con:r=con.execute('SELECT sid FROM recovery_keys WHERE token=? AND expires>?',(hashlib.sha256(token.strip().encode()).hexdigest(),time.time())).fetchone()
                if not r or not get(r['sid']):raise ValueError('This recovery key is invalid or expired.')
                self.new_cookie=r['sid'];return self.send(obj={'message':'Your saved reading is open.','redirect':'result.html'})
            elif path=='/api/delete':
                if body.get('confirmation')!='DELETE':raise ValueError('Confirm deletion first.')
                purge_session(sid);self.clear_cookie=True
                return self.send(obj={'message':'This reading and its saved files have been deleted.'})
            elif path=='/api/logout':
                self.clear_cookie=True;return self.send(obj={'message':'You have signed out on this browser.'})
            elif path=='/api/recover':
                email=body.get('email','')
                if not isinstance(email,str):raise ValueError('Please enter a valid email address.')
                email=email.strip().lower()
                with connection() as con:rows=con.execute('SELECT id,data FROM sessions ORDER BY updated DESC').fetchall()
                matches=[r for r in rows if json.loads(r['data']).get('email')==email and email]
                if matches:recovery_mail(matches[0]['id'])
                return self.send(obj={'message':('If a reading is associated with this email, a secure access message has been queued for delivery.' if mail_configured() else 'Email recovery is not connected yet. Use your private recovery key below, or contact support. No external email was sent.')})
            elif path=='/api/resend-ebook':
                email=body.get('email','').strip().lower()
                book_id=body.get('book_id','').strip()
                session_id=body.get('session_id','').strip()
                name=body.get('name','Valued Reader').strip()
                if not email or '@' not in email:raise ValueError('Please enter a valid email address.')
                if not book_id or book_id not in EBOOK_DELIVERY:raise ValueError('Invalid book selection.')
                order_id='resend_'+hashlib.sha256(f'{email}:{book_id}:{time.time()}'.encode()).hexdigest()[:16]
                res=deliver_ebook(order_id,email,name,book_id,session_id=session_id)
                return self.send(obj={'message':f"Your ebook has been sent to {email}.",'status':res['status']})
            elif path=='/api/support':
                message=body.get('message','')
                if not isinstance(message,str):raise ValueError('Please enter your message.')
                message=message.strip()
                if not 10<=len(message)<=2000:raise ValueError('Please write between 10 and 2,000 characters')
                reply=body.get('email') or d.get('email','')
                if reply:_,reply=valid_identity(body.get('name') or d.get('answers',{}).get('name') or 'Reader',reply)
                category=body.get('category','general')
                if category not in ['general','access','technical','refund','privacy']:raise ValueError('Choose a contact topic.')
                mid=secrets.token_hex(16);recipient=CONFIG.get('support_email') or 'Local support inbox'
                message=f'Reply address: {reply}\nTopic: {category}\n\n'+message
                with connection() as con:con.execute('INSERT INTO mail(id,sid,recipient,subject,body,due,kind,created,delivery_status) VALUES(?,?,?,?,?,?,?,?,?)',(mid,sid,recipient,'Support request '+mid[:8],message,time.time(),'support',time.time(),'pending' if mail_configured() and CONFIG.get('support_email') else 'local'))
                return self.send(obj={'reference':mid[:8],'message':('Your request is queued for support. Reference: ' if mail_configured() and CONFIG.get('support_email') else 'Your request is saved in this preview. External support delivery is not connected. Reference: ')+mid[:8]})
            elif path=='/api/auth/register':
                name,email=valid_identity(body.get('name'),body.get('email'))
                password=body.get('password','')
                if not isinstance(password,str) or len(password)<8 or len(password)>128:
                    raise ValueError('Please choose a password with at least 8 characters.')
                existing=get_user_by_email(email)
                if existing:
                    raise ValueError('An account with this email already exists. Please sign in or use password recovery.')
                u,created=create_or_get_user(email,password,name)
                if not created:raise ValueError('An account with this email already exists. Please sign in.')
                if d.get('user_id') and d['user_id']!=u['id']:
                    sid=new_session();self.new_cookie=sid;d=get(sid)
                if SUPABASE.is_configured():
                    try:SUPABASE.sign_up(email,password,name)
                    except Exception as ex:print(f"[SUPABASE SIGNUP ERROR] {ex}",flush=True)
                link_user_sessions(u['id'],email,sid)
                def setup_session(x):
                    x.update(user_id=u['id'],email=email,started=True)
                    x['answers']['name']=name
                update(sid,setup_session)
                if mail_configured():
                    send_auth_mail(email,'Rabbi David | Welcome to your account',f"Shalom {name},\n\nYour account is ready. It gives you one place to return to your readings.\n\n{public_origin()}/account.html\n\nUse your email address and password to sign in.\n\nWith warmth,\nThe Rabbi David Team",'welcome')
                return self.send(obj={'user':safe_user(u),'readings':get_user_readings_list(u['id']),'message':'Account created successfully.'})
            elif path=='/api/auth/login':
                email=body.get('email','')
                password=body.get('password','')
                if not isinstance(email,str) or not isinstance(password,str):
                    raise ValueError('Please enter your email and password.')
                email=email.strip().lower()
                u=get_user_by_email(email)
                if not u or not u.get('password_hash') or not verify_password(password,u['salt'],u['password_hash']):
                    raise ValueError('Invalid email or password.')
                if d.get('user_id') and d['user_id']!=u['id']:
                    sid=new_session();self.new_cookie=sid;d=get(sid)
                link_user_sessions(u['id'],email,sid)
                update(sid,lambda x:x.update(user_id=u['id'],email=email))
                return self.send(obj={'user':safe_user(u),'readings':get_user_readings_list(u['id']),'message':'Signed in successfully.'})
            elif path=='/api/auth/logout':
                self.clear_cookie=True
                new_sid=new_session();self.new_cookie=new_sid
                return self.send(obj={'message':'You have been signed out.'})
            elif path=='/api/auth/status':
                curr=self.current_user()
                readings=get_user_readings_list(curr['id']) if curr else []
                return self.send(obj={'enabled':True,'user':safe_user(curr),'readings':readings})
            elif path=='/api/auth/open':
                reading_id=body.get('reading_id','')
                curr=self.current_user()
                if not curr:raise ValueError('Please sign in to open your reading.')
                with connection() as con:
                    row=con.execute('SELECT id,data FROM sessions WHERE id=? AND user_id=?',(reading_id,curr['id'])).fetchone()
                if not row:raise ValueError('Reading not found in your account.')
                self.new_cookie=reading_id
                reading_data=json.loads(row['data'])
                return self.send(obj={'ready':reading_data.get('status')=='ready','id':reading_id})
            elif path=='/api/auth/reset-request':
                email=body.get('email','')
                if not isinstance(email,str) or '@' not in email:
                    raise ValueError('Please enter a valid email address.')
                email=email.strip().lower()
                u=get_user_by_email(email)
                if u:
                    token=secrets.token_urlsafe(32)
                    with connection() as con:
                        con.execute('DELETE FROM password_resets WHERE user_id=?',(u['id'],))
                        con.execute('INSERT INTO password_resets(token,user_id,expires) VALUES(?,?,?)',(token,u['id'],time.time()+3600))
                    reset_url=f"{public_origin()}/account.html?reset_token={token}"
                    send_auth_mail(email,'Rabbi David | Reset your password',f"Shalom,\n\nYou requested a new password. Choose one using the button below:\n\n{reset_url}\n\nThis link expires in 1 hour. If you did not request it, ignore this email; your password will stay the same.\n\nWith warmth,\nThe Rabbi David Team",'password_reset')
                    # Login and reset use the local account. A second Supabase recovery
                    # would change a different credential and confuse the recipient.
                return self.send(obj={'message':'If this email belongs to an account, recovery instructions have been sent.'})
            elif path=='/api/auth/reset-confirm':
                token=body.get('token','')
                password=body.get('password','')
                if not isinstance(password,str) or len(password)<8 or len(password)>128:
                    raise ValueError('Please choose a password with at least 8 characters.')
                if not isinstance(token,str) or not token:
                    raise ValueError('Invalid or missing reset token.')
                with connection() as con:
                    r=con.execute('SELECT user_id FROM password_resets WHERE token=? AND expires>?',(token,time.time())).fetchone()
                    if not r:raise ValueError('This reset link is invalid or has expired.')
                    user_id=r['user_id']
                    salt,pw_hash=hash_password(password)
                    con.execute('UPDATE users SET password_hash=?,salt=?,updated=? WHERE id=?',(pw_hash,salt,time.time(),user_id))
                    con.execute('DELETE FROM password_resets WHERE user_id=?',(user_id,))
                return self.send(obj={'message':'Your password has been updated. You can now sign in.'})
            elif path=='/api/auth/verify-email':
                token=body.get('token','')
                if not isinstance(token,str) or not token:raise ValueError('Invalid verification token.')
                with connection() as con:
                    r=con.execute('SELECT id FROM users WHERE verification_token=?',(token,)).fetchone()
                    if not r:raise ValueError('Invalid verification token.')
                    con.execute('UPDATE users SET email_verified=1,updated=? WHERE id=?',(time.time(),r['id']))
                return self.send(obj={'message':'Email successfully verified.'})
            elif path=='/api/internal/grant-tier':
                email=body.get('email','').strip().lower()
                session_id=body.get('session_id','').strip()
                tier=body.get('tier','').strip().lower()
                order_id=body.get('order_id') or ('ord_'+secrets.token_hex(8))
                provider_id=body.get('provider_id','')
                amount=int(body.get('amount',0))
                if tier not in ['reading','personal']:
                    raise ValueError('Invalid tier: choose reading or personal')
                if not email and not session_id:
                    raise ValueError('Must provide email or session_id')
                target_sid=None
                with connection() as con:
                    if session_id:
                        r=con.execute('SELECT id,data FROM sessions WHERE id=?',(session_id,)).fetchone()
                        if r:target_sid=r['id']
                    if not target_sid and email:
                        rows=con.execute('SELECT id,data FROM sessions ORDER BY updated DESC').fetchall()
                        for row in rows:
                            d_row=json.loads(row['data'])
                            if d_row.get('email')==email:
                                target_sid=row['id'];break
                if not target_sid:
                    target_sid=new_session()
                    u,_=create_or_get_user(email)
                    update(target_sid,lambda x:x.update(started=True,email=email,user_id=u['id']))
                def upgrade_tier(x):
                    x['tier']=tier
                    if email and not x.get('email'):x['email']=email
                    if tier=='personal' and not x.get('plan'):x['plan_status']='preparing'
                with LOCK:
                    d=update(target_sid,upgrade_tier)
                    sync_delivery(target_sid)
                    event(target_sid,'grant_tier_'+tier)
                    if tier=='personal' and d.get('plan_status')=='preparing':
                        schedule(plan_job,target_sid,d['revision'])
                with connection() as con:
                    u=get_user_by_email(email)
                    uid=u['id'] if u else None
                    con.execute('INSERT OR REPLACE INTO orders(id,session_id,email,book_id,amount,currency,created,delivery_status,provider_id,user_id) VALUES(?,?,?,?,?,?,?,?,?,?)',
                                (order_id,target_sid,email,'tier_'+tier,amount,'usd',time.time(),'completed',provider_id,uid))
                if SUPABASE and SUPABASE.is_configured():
                    try:POOL.submit(lambda: SUPABASE.upsert_order({'id':order_id,'session_id':target_sid,'email':email,'book_id':'tier_'+tier,'amount':amount,'currency':'usd','delivery_status':'completed','provider_id':provider_id,'user_id':uid,'created':time.time()}))
                    except Exception as ex:print(f"[SUPABASE GRANT TIER ORDER SYNC ERROR] {ex}",flush=True)
                return self.send(obj={'success':True,'tier':tier,'sid':target_sid})
            elif path=='/api/new':
                self.new_cookie=new_session();return self.send(obj=safe_state(get(self.new_cookie)))
            else:return self.send(404,{'error':'Not found'})
            return self.send(obj=safe_state(d))
        except CapacityError as e:return self.send(429,{'error':str(e)},headers={'Retry-After':'60'})
        except ValueError as e:return self.send(400,{'error':str(e)})
        except Exception as e:
            print(f"[SERVER POST ERROR] {e}", flush=True)
            import traceback; traceback.print_exc()
            return self.send(500,{'error':'Something could not be saved. Your last saved answers are safe.'})

def main():
    global AI_ENABLED,VOICE_ENABLED
    p=argparse.ArgumentParser()
    p.add_argument('--config',default=os.environ.get('CONFIG_PATH'))
    p.add_argument('--data',default=os.environ.get('DATA_DIR','./antigravity-data'))
    p.add_argument('--host',default=os.environ.get('HOST','0.0.0.0'))
    p.add_argument('--port',type=int,default=int(os.environ.get('PORT',8100)))
    p.add_argument('--offline',action='store_true')
    p.add_argument('--enable-voice',action='store_true',default=os.environ.get('ENABLE_VOICE','0')=='1')
    args=p.parse_args()
    config={}
    if args.config and Path(args.config).is_file():
        config=json.loads(Path(args.config).read_text(encoding='utf-8'))
    elif Path('config.json').is_file():
        config=json.loads(Path('config.json').read_text(encoding='utf-8'))
    elif Path('../work/rabbi-david-private/config.json').is_file():
        config=json.loads(Path('../work/rabbi-david-private/config.json').read_text(encoding='utf-8'))
    if os.environ.get('OPENROUTER_KEY'):
        config['openrouter_key']=os.environ['OPENROUTER_KEY']
    elif os.environ.get('OPENROUTER_API_KEY'):
        config['openrouter_key']=os.environ['OPENROUTER_API_KEY']

    if os.environ.get('OPENROUTER_MODEL'):
        config['openrouter_model']=os.environ['OPENROUTER_MODEL']
    elif not config.get('openrouter_model') or 'ling-3.0' in config.get('openrouter_model',''):
        config['openrouter_model']='~deepseek/deepseek-flash-latest'

    if 'graceful_fallback' not in config:
        config['graceful_fallback']=True

    if os.environ.get('AI33_KEY'):
        config['ai33_key']=os.environ['AI33_KEY']
    if os.environ.get('AI33_VOICE_ID'):
        config['ai33_voice_id']=os.environ['AI33_VOICE_ID']
    AI_ENABLED=not args.offline
    VOICE_ENABLED=args.enable_voice
    for field in ['resend_api_key','smtp_host','smtp_port','smtp_username','smtp_password','mail_from','support_email','supabase_url','supabase_key','supabase_anon_key','supabase_service_role_key']:
        if os.environ.get(field.upper()):config[field]=os.environ[field.upper()]
    config.setdefault('supabase_url','https://gkihlvkdkciqpkrhbunv.supabase.co')
    config.setdefault('supabase_key','eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdraWhsdmtka2NpcXBrcmhidW52Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4OTU1NDgxOCwiZXhwIjoyMTA1MTMwODE4fQ.XlGVP58ldWp7_6Yn9lE_nkNJFWo6N_RswQ6Uy7pVMc8')
    config.setdefault('supabase_service_role_key','eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdraWhsdmtka2NpcXBrcmhidW52Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4OTU1NDgxOCwiZXhwIjoyMTA1MTMwODE4fQ.XlGVP58ldWp7_6Yn9lE_nkNJFWo6N_RswQ6Uy7pVMc8')
    if config.get('smtp_password'):
        config.setdefault('smtp_host','smtp.resend.com')
        config.setdefault('smtp_port',587)
        config.setdefault('smtp_username','resend')
        config.setdefault('mail_from','Rabbi David <delivery@rabbidavid.org>')
        config.setdefault('support_email','soporte@rabbidavid.org')
    if os.environ.get('PUBLIC_ORIGIN'):config['public_origin']=os.environ['PUBLIC_ORIGIN'].rstrip('/')
    elif not config.get('public_origin') and (os.environ.get('PRODUCTION')=='1' or os.environ.get('RENDER') or os.environ.get('RENDER_EXTERNAL_HOSTNAME')):
        config['public_origin']='https://rabbidavid.org' 
    if os.environ.get('FREE_TESTING') is not None:
        config['free_testing']=os.environ['FREE_TESTING'].lower() in ('1','true','yes')
    elif config.get('free_testing') is None:
        config['free_testing']=True
    if os.environ.get('PRODUCTION')=='1' and not config.get('public_origin'):p.error('PUBLIC_ORIGIN is required in production')
    init(config,args.data,args.port)
    threading.Thread(target=poll_voices,daemon=True).start()
    print(f'Server listening on http://{args.host}:{PORT} | Voice: {VOICE_ENABLED}',flush=True)
    try:ThreadingHTTPServer((args.host,PORT),Handler).serve_forever()
    except KeyboardInterrupt:STOP.set()

if __name__=='__main__':main()

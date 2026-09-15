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
from providers import generate_reading,generate_plan,generate_followup,submit_voice,poll_voice,download_audio,ProviderError
from documents import reading_pdf,plan_pdf
from source_library import SOURCE_BY_ID
from email.message import EmailMessage

ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock();POOL=BoundedExecutor();STOP=threading.Event()
CONFIG={};DATA=None;DB=None;PORT=8100;AI_ENABLED=True;VOICE_ENABLED=False
EMAIL_RESOLVER=None
CATALOG=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))

@contextmanager
def connection():
    con=sqlite3.connect(DB,timeout=10);con.row_factory=sqlite3.Row
    try:
        with con:yield con
    finally:con.close()

def init(config,data,port=8100):
    global CONFIG,DATA,DB,PORT
    CONFIG=config;origins(config,port);DATA=Path(data);DATA.mkdir(parents=True,exist_ok=True);(DATA/'audio').mkdir(exist_ok=True);DB=DATA/'state.sqlite';PORT=port
    with connection() as con:
        con.executescript('''CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,data TEXT NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mail(id TEXT PRIMARY KEY,sid TEXT NOT NULL,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,due REAL NOT NULL,kind TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS access(token TEXT PRIMARY KEY,sid TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,sid TEXT,event TEXT,created REAL);''')
        columns={r[1] for r in con.execute('PRAGMA table_info(mail)')}
        if 'delivery_status' not in columns:con.execute("ALTER TABLE mail ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'local'")
        con.execute("UPDATE mail SET delivery_status='needs_review' WHERE delivery_status='sending'")
        con.execute('CREATE TABLE IF NOT EXISTS recovery_keys(token TEXT PRIMARY KEY,sid TEXT NOT NULL,expires REAL NOT NULL)')
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

def new_session():
    sid=secrets.token_urlsafe(32)
    with connection() as con:con.execute('INSERT INTO sessions VALUES(?,?,?)',(sid,json.dumps(blank()),time.time()))
    return sid

def get(sid):
    with connection() as con:r=con.execute('SELECT data FROM sessions WHERE id=?',(sid,)).fetchone()
    return json.loads(r['data']) if r else None

def update(sid,fn):
    with LOCK:
        with connection() as con:
            r=con.execute('SELECT data FROM sessions WHERE id=?',(sid,)).fetchone()
            if not r:raise ValueError('Session not found')
            d=json.loads(r['data']);fn(d)
            con.execute('UPDATE sessions SET data=?,updated=? WHERE id=?',(json.dumps(d),time.time(),sid))
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
    return (os.environ.get('PUBLIC_ORIGIN') or CONFIG.get('public_origin') or f'http://127.0.0.1:{PORT}').rstrip('/')

def recovery_mail(sid):
    d=get(sid); token=secrets.token_urlsafe(32)
    with connection() as con:
        con.execute('DELETE FROM access WHERE expires<?',(time.time(),))
        con.execute('INSERT INTO access VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),sid,time.time()+900))
    # Queue only newly requested mail when SMTP is configured; existing local previews stay local.
    mid=secrets.token_hex(16)
    with connection() as con:
        con.execute('INSERT INTO mail(id,sid,recipient,subject,body,due,kind,created,delivery_status) VALUES(?,?,?,?,?,?,?,?,?)',(mid,sid,d['email'],'Your secure access link',f'Open {public_origin()}/access?token={token}\nThis link expires in 15 minutes and works once.',time.time(),'access',time.time(),'pending' if mail_configured() else 'local'))

def sync_delivery(sid):
    d=get(sid)
    if not d or d.get('status')!='ready':return
    view,preview=reading_view(d['reading'],d['tier'])
    parts=['A personal reading for '+d['answers']['name'],view['title'],view['summary'],view['insight']]
    for item in view.get('evidence',[]):parts.extend(['How your answers connect',item['interpretation']])
    step=view.get('first_step')
    if step:parts.extend(['Your first practical step',step['action'],step['why'],step['reflection']])
    for section in view['sections']:parts.extend([section['title'],section['text']])
    if d['tier']=='free':parts.append('This is your free opening reflection, approximately 40% of your reading. Your saved personal space explains the complete reading and optional plan.')
    parts.append('Return with your private recovery key or request an email access link from the website. No purchase was made in this preview.'+('' if mail_configured() else ' Delivery status is shown in your saved reading.'))
    mail(sid,'reading_'+d['tier'],'Your Rabbi David reading is ready','\n\n'.join(p for p in parts if p))
    if d['marketing']:
        for days,subject,body in [(1,'How did your first reflection feel?','Was the reading clear? Reply with what felt useful or what did not fit. You can return to your personal space whenever you wish.'),(5,'What would you like to explore next?','What have you noticed since your reading? Your personal space includes an optional book suggestion related to your chosen priority.')]:
            mail(sid,'followup_'+str(days),subject,body+'\nYou can turn off follow-ups in your personal space.',time.time()+days*86400)

def prepare_plan_delivery(sid):
    """Prepare the actual attachment locally; no external delivery is claimed."""
    d=get(sid)
    if d['tier']!='personal' or not d.get('plan'):return
    pdf=plan_pdf(d)
    mid=hashlib.sha256(f'{sid}:{d["revision"]}:plan'.encode()).hexdigest()
    message=EmailMessage()
    message['To']=d['email']
    message['Subject']='Your personal fourteen-day plan'
    message.set_content(f"{d['answers']['name']}, your personal plan is attached as a PDF. Read the introduction, then begin with Day 1. You can also download it from your saved reading.\n\nKeep this plan for your personal reference.")
    message.add_attachment(pdf,maintype='application',subtype='pdf',filename='your-personal-14-day-plan.pdf')
    directory=DATA/'outbox';directory.mkdir(exist_ok=True)
    target=directory/(mid+'.eml');temporary=directory/(mid+'.tmp')
    temporary.write_bytes(message.as_bytes());temporary.replace(target)
    mail(sid,'plan',message['Subject'],'Your personal eighteen-page plan is attached to the prepared email. Download the PDF from your saved reading. Delivery status is shown in your saved reading.')

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
    s['voice']['available']=(DATA/'audio'/f'{s.get("audio_file", "none")}').is_file() if s.get('audio_file') else False
    intro=d.get('intro',{'status':'not_requested'})
    s['intro']={k:v for k,v in intro.items() if k in ['status','error','progress']}
    s['intro']['available']=bool(d.get('intro_file') and (DATA/'audio'/d['intro_file']).is_file())
    s.pop('intro_file',None)
    s.pop('audio_file',None);s.pop('usage',None)
    s.pop('reading_diagnostic',None);s.pop('plan_diagnostic',None)
    s['email_delivery_enabled']=bool(CONFIG.get('smtp_host') and CONFIG.get('mail_from'))
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
        script=f"{name}, welcome to your personal reading. "+d['reading']['summary']+' '+d['reading']['insight']+' '
        script+=' '.join(item['interpretation'] for item in d['reading'].get('evidence',[]))+' '
        step=d['reading'].get('first_step')
        if step:script+=' '.join(step[k] for k in ('action','why','reflection'))+' '
        # The full reading stays in the written report; narration gives a coherent
        # spoken selection without turning a deeper report into a 20-minute audio.
        def spoken_excerpt(text):
            paragraph=text.split('\n\n')[0]
            sentences=re.split(r'(?<=[.!?])\s+',paragraph)
            selected=[]
            for sentence in sentences:
                if selected and len((' '.join(selected+[sentence])).split())>150:break
                selected.append(sentence)
            return ' '.join(selected)
        script+=' '.join(spoken_excerpt(s['text']) for s in d['reading']['sections'])
        script+=' For the next fourteen days, your written plan invites you to take one small step at a time. '+d['plan'][0]['action']+' At the end of each week, notice what felt useful and what you would change. There is no need to rush. You can return to this reading whenever you wish.'
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
    script=f'{name}, your answers are safely saved. Your personal plan is being prepared around the priorities you shared. You can stay here or return to your reading space later. There is nothing more you need to fill in. Thank you for taking this time for yourself.'
    update(sid,lambda x:x.update(intro={'status':'submitting','script':script}))
    try:
        task=submit_voice(CONFIG,script,'rabbi-welcome-'+secrets.token_hex(6))
        update(sid,lambda x:x['intro'].update(status='processing',task_id=task,submitted_at=time.time()))
    except Exception:update(sid,lambda x:x['intro'].update(status='needs_review',error='The spoken welcome needs a provider check. Your plan preparation continues.'))

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
            def done(x):
                x['intro_file' if field=='intro' else 'audio_file']=name
                x[field].update(status='ready',progress=100,credit_cost=task.get('credit_cost'),poll_errors=0)
            update(sid,done)
        else:update(sid,lambda x:x[field].update(progress=task.get('progress',0),poll_errors=0,next_poll_at=now+8))
    except Exception:
        count=v.get('poll_errors',0)+1
        update(sid,lambda x:x[field].update(poll_errors=count,next_poll_at=now+min(300,8*2**min(count,6))))
        event(sid,'voice_poll_error:'+field)

def mail_configured():return bool(CONFIG.get('smtp_host') and CONFIG.get('mail_from'))

def dispatch_mail_once():
    if not mail_configured():return
    from email.parser import BytesParser
    import smtplib,ssl
    with LOCK:
        with connection() as con:
            row=con.execute("SELECT * FROM mail WHERE due<=? AND delivery_status='pending' ORDER BY created LIMIT 1",(time.time(),)).fetchone()
            if not row:return
            con.execute("UPDATE mail SET delivery_status='sending' WHERE id=?",(row['id'],))
    try:
        attachment=DATA/'outbox'/(row['id']+'.eml')
        message=BytesParser().parsebytes(attachment.read_bytes()) if row['kind']=='plan' and attachment.is_file() else EmailMessage()
        if not message.get('To'):
            message['To']=row['recipient'];message['Subject']=row['subject'];message.set_content(row['body'])
        message['From']=CONFIG['mail_from'];message['Message-ID']='<'+row['id']+'@'+CONFIG['mail_from'].split('@')[-1]+'>'
        with smtplib.SMTP(CONFIG['smtp_host'],int(CONFIG.get('smtp_port',587)),timeout=20) as client:
            client.starttls(context=ssl.create_default_context())
            if CONFIG.get('smtp_username'):client.login(CONFIG['smtp_username'],CONFIG.get('smtp_password',''))
            client.send_message(message)
        status='sent'
    except Exception:status='needs_review'
    with connection() as con:con.execute('UPDATE mail SET delivery_status=? WHERE id=?',(status,row['id']))


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
            if path=='/api/state':return self.send(obj=safe_state(get(sid)))
            if path=='/api/catalog':return self.send(obj=[b for b in CATALOG if b.get('active',True)])
            if path=='/api/practices':return self.send(obj=PRACTICES)
            if path=='/api/config':return self.send(obj=dict(version=VERSION,model=CONFIG.get('openrouter_model',''),mode='preview',payments=False,email='smtp' if mail_configured() else 'local',support='email' if mail_configured() and CONFIG.get('support_email') else 'local',ai=AI_ENABLED,voice=VOICE_ENABLED,free_testing=CONFIG.get('free_testing') is True))
            if path=='/api/export':
                return self.send(obj=safe_state(get(sid)),headers={'Content-Disposition':'attachment; filename="my-reading-data.json"'})
            if path=='/api/inbox':
                with connection() as con:rows=con.execute('SELECT id,recipient,subject,body,due,kind,delivery_status FROM mail WHERE sid=? ORDER BY created DESC',(sid,)).fetchall()
                items=[dict(r) for r in rows]
                for item in items:
                    if item['kind']=='plan' and (DATA/'outbox'/(item['id']+'.eml')).is_file():item['attachment_preview']='/api/plan-email?id='+item['id']
                return self.send(obj=items)
            if path=='/api/plan-pdf':
                d=get(sid)
                if d['tier']!='personal':return self.send(403,{'error':'Your personal plan is required'})
                if d['status']!='ready' or not d.get('plan'):return self.send(409,{'error':'Your plan is still being prepared'})
                return self.send(body=plan_pdf(d),mime='application/pdf',headers={'Content-Disposition':'attachment; filename="your-personal-14-day-plan.pdf"'})
            if path=='/api/plan-email':
                mid=urllib.parse.parse_qs(u.query).get('id',[''])[0]
                with connection() as con:owned=con.execute("SELECT id FROM mail WHERE id=? AND sid=? AND kind='plan'",(mid,sid)).fetchone()
                if not owned:return self.send(404,{'error':'Email preview not found'})
                file=DATA/'outbox'/(owned['id']+'.eml')
                if not file.is_file():return self.send(404,{'error':'Email preview is not ready'})
                return self.send(body=file.read_bytes(),mime='message/rfc822',headers={'Content-Disposition':'attachment; filename="your-plan-email.eml"'})
            if path=='/api/pdf':
                d=get(sid)
                if d['status']!='ready':return self.send(409,{'error':'Your reading is not ready yet'})
                return self.send(body=reading_pdf(d),mime='application/pdf',headers={'Content-Disposition':'attachment; filename="your-rabbi-david-reading.pdf"'})
            if path=='/api/audio':
                d=get(sid)
                if not d.get('audio_file') or d['voice']['status']!='ready':return self.send(404,{'error':'Audio is not ready'})
                return self.send_file(DATA/'audio'/d['audio_file'],mime='audio/mpeg',private=True)
            if path=='/api/welcome':
                d=get(sid)
                if not d.get('intro_file') or d.get('intro',{}).get('status')!='ready':return self.send(404,{'error':'Welcome is not ready'})
                return self.send_file(DATA/'audio'/d['intro_file'],mime='audio/mpeg',private=True)
            if path=='/api/transcript':
                d=get(sid)
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
            if path.startswith('/api/'):return self.send(404,{'error':'Not found'})
            if path=='/':path='/index.html'
            f=(ROOT/'public'/urllib.parse.unquote(path.lstrip('/'))).resolve()
            if not f.is_relative_to((ROOT/'public').resolve()) or not f.is_file():return self.send(404,{'error':'Not found'})
            return self.send_file(f)
        except Exception:return self.send(500,{'error':'Something could not be loaded. Please try again.'})
    def do_POST(self):
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
                def enroll(x):
                    if x.get('started'):return
                    x.update(started=True,email=email,marketing=body.get('marketing') is True,enrolled_at=time.time());x['answers']['name']=name
                d=update(sid,enroll);event(sid,'test_started');sync_delivery(sid)
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
            elif path=='/api/new':
                self.new_cookie=new_session();return self.send(obj=safe_state(get(self.new_cookie)))
            else:return self.send(404,{'error':'Not found'})
            return self.send(obj=safe_state(d))
        except CapacityError as e:return self.send(429,{'error':str(e)},headers={'Retry-After':'60'})
        except ValueError as e:return self.send(400,{'error':str(e)})
        except Exception:return self.send(500,{'error':'Something could not be saved. Your last saved answers are safe.'})

def main():
    global AI_ENABLED,VOICE_ENABLED
    p=argparse.ArgumentParser()
    p.add_argument('--config',default=os.environ.get('CONFIG_PATH'))
    p.add_argument('--data',default=os.environ.get('DATA_DIR','./antigravity-data'))
    p.add_argument('--host',default=os.environ.get('HOST','127.0.0.1'))
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
    for field in ['smtp_host','smtp_port','smtp_username','smtp_password','mail_from','support_email']:
        if os.environ.get(field.upper()):config[field]=os.environ[field.upper()]
    if os.environ.get('PUBLIC_ORIGIN'):config['public_origin']=os.environ['PUBLIC_ORIGIN'].rstrip('/')
    if os.environ.get('FREE_TESTING'):config['free_testing']=os.environ['FREE_TESTING'].lower()=='true'
    if os.environ.get('PRODUCTION')=='1' and not config.get('public_origin'):p.error('PUBLIC_ORIGIN is required in production')
    init(config,args.data,args.port)
    threading.Thread(target=poll_voices,daemon=True).start()
    print(f'Server listening on http://{args.host}:{PORT} | Voice: {VOICE_ENABLED}',flush=True)
    try:ThreadingHTTPServer((args.host,PORT),Handler).serve_forever()
    except KeyboardInterrupt:STOP.set()

if __name__=='__main__':main()

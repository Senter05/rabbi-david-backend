"""Bounded admission, exact origins and provider request budgets."""
import os,sqlite3,time,threading,urllib.parse
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor

class CapacityError(ValueError): pass

class BoundedExecutor:
    def __init__(self,workers=3,capacity=12):
        self.pool=ThreadPoolExecutor(max_workers=workers)
        self.slots=threading.BoundedSemaphore(capacity)
    def submit(self,fn,*args,**kwargs):
        if not self.slots.acquire(blocking=False):raise CapacityError('Preparation is busy. Please try again shortly; your answers are saved.')
        try:future=self.pool.submit(fn,*args,**kwargs)
        except Exception:self.slots.release();raise
        future.add_done_callback(lambda _:self.slots.release())
        return future

def origins(config,port):
    raw=os.environ.get('PUBLIC_ORIGIN') or config.get('public_origin','')
    extra=os.environ.get('ALLOWED_ORIGINS','').split(',')
    values={f'http://localhost:{port}',f'http://127.0.0.1:{port}'}
    for item in [raw,*extra]:
        item=item.strip().rstrip('/')
        if not item:continue
        u=urllib.parse.urlsplit(item)
        if u.scheme not in ('http','https') or not u.netloc or u.path or u.query or u.fragment or u.username or '*' in item:raise ValueError('Configure exact HTTP(S) origins without paths or wildcards')
        values.add(item)
    return values

def reserve(db,bucket,limit,seconds=86400):
    if limit<=0:raise CapacityError('New preparation is temporarily paused. Please try again later.')
    window=int(time.time()//seconds)
    with closing(sqlite3.connect(db,timeout=10)) as con, con:
        con.execute('CREATE TABLE IF NOT EXISTS quotas(bucket TEXT,window INTEGER,used INTEGER,PRIMARY KEY(bucket,window))')
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT used FROM quotas WHERE bucket=? AND window=?',(bucket,window)).fetchone()
        if row and row[0]>=limit:raise CapacityError('The preparation limit has been reached. Please try again later.')
        con.execute('INSERT INTO quotas VALUES(?,?,1) ON CONFLICT(bucket,window) DO UPDATE SET used=used+1',(bucket,window))
        con.execute('DELETE FROM quotas WHERE window<? AND bucket=?',(window-2,bucket))

class ProviderBudget:
    def __init__(self,db,config):self.db=db;self.config=config
    def __call__(self,url,data):
        if not data:return
        host=urllib.parse.urlsplit(url).hostname
        if host=='openrouter.ai':kind='text';default=100
        elif host=='api.ai33.pro' and '/text-to-speech' in url:kind='voice';default=10
        else:return
        if os.environ.get('PAUSE_GENERATION')=='1':raise CapacityError('New preparation is temporarily paused.')
        reserve(self.db,'provider:'+kind,int(os.environ.get('MAX_'+kind.upper()+'_REQUESTS_PER_DAY',self.config.get('max_'+kind+'_requests_per_day',default))))

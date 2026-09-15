"""Owner-only local operations. Never exposed as HTTP administration."""
import argparse,json,sqlite3,time,shutil
from pathlib import Path
from contextlib import closing

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True)
    p.add_argument('action',choices=['status','voice-resume','mail-retry'])
    p.add_argument('--id');p.add_argument('--field',choices=['voice','intro'],default='voice')
    p.add_argument('--confirmed-unsent',action='store_true');args=p.parse_args()
    db=Path(args.data).resolve()/'state.sqlite'
    if not db.is_file():p.error('No existing application database found')
    with closing(sqlite3.connect(db)) as con,con:
        if args.action=='status':
            sessions=con.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
            mail=dict(con.execute('SELECT delivery_status,COUNT(*) FROM mail GROUP BY delivery_status'))
            review=[]
            for sid,raw in con.execute('SELECT id,data FROM sessions'):
                d=json.loads(raw)
                for field in ['voice','intro']:
                    if d.get(field,{}).get('status')=='needs_review':review.append({'session':sid,'field':field,'existing_task':bool(d[field].get('task_id'))})
            print(json.dumps({'sessions':sessions,'mail_counts':mail,'audio_needing_review':review},indent=2))
        elif args.action=='voice-resume':
            row=con.execute('SELECT data FROM sessions WHERE id=?',(args.id,)).fetchone()
            if not row:p.error('Session not found')
            d=json.loads(row[0]);v=d.get(args.field,{})
            if v.get('status')!='needs_review' or not v.get('task_id'):p.error('Only an existing provider task can resume; check the provider manually if no task ID was saved')
            v.update(status='processing',submitted_at=time.time(),next_poll_at=0,poll_errors=0,error=None)
            con.execute('UPDATE sessions SET data=? WHERE id=?',(json.dumps(d),args.id));print('Polling of the existing task resumed; no new recording submitted.')
        else:
            if not args.confirmed_unsent:p.error('First verify that the provider did not send this message, then use --confirmed-unsent')
            changed=con.execute("UPDATE mail SET delivery_status='pending' WHERE id=? AND delivery_status='needs_review'",(args.id,)).rowcount
            print('Messages queued:',changed)
if __name__=='__main__':main()

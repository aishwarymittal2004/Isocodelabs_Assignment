"""Five visibly fictional, non-contactable *project contact cards*.

Not real staff accounts, not monitored phone/email addresses. Development only.
Default is read-only. Uses stable IDs so repeated runs never duplicate cards.

Run from backend root:
  python scripts/seed_example_salespeople.py
  python scripts/seed_example_salespeople.py --apply
"""
import argparse
import os
import sys
import uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from app.core import SessionLocal,engine,ENVIRONMENT,now
from app.models import Project,ProjectSalesperson,AuditEvent

CONTACTS=[
  ('fictional-sahaj-grove','Kavya Shah (Demo)','+910000000101','kavya.shah@example.test'),
  ('fictional-sahaj-grove','Arjun Mehta (Demo)','+910000000102','arjun.mehta@example.test'),
  ('fictional-metrovista-square','Riya Desai (Demo)','+910000000103','riya.desai@example.test'),
  ('fictional-metrovista-square','Dev Patel (Demo)','+910000000104','dev.patel@example.test'),
  ('fictional-banyan-crest','Neha Trivedi (Demo)','+910000000105','neha.trivedi@example.test'),
]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    if ENVIRONMENT=='production':raise SystemExit('Demo contacts cannot be added in production.')
    if engine.url.drivername.startswith('postgresql'):
        if engine.url.host not in ('localhost','127.0.0.1','::1') or engine.url.database!='sitepilot':
            raise SystemExit('Only local PostgreSQL sitepilot is allowed.')
    elif not(engine.url.drivername.startswith('sqlite') and os.getenv('SITEPILOT_TEST_DB')=='1'):
        raise SystemExit('Unsupported target DB. No data written.')
    print('Target DB:',engine.url.database,'@',engine.url.host)
    print('These five names are fictional; phone numbers are deliberately invalid and email domain example.test is not monitored.')
    with SessionLocal() as db:
        for pid,name,phone,email in CONTACTS:
            p=db.get(Project,pid)
            if p is None or 'fictional demo' not in p.name.casefold():
                raise SystemExit(f'Refusing: required fictional project {pid} not present or has unexpected name.')
            sid=str(uuid.uuid5(uuid.NAMESPACE_DNS,'sitepilot-demo-contact:'+pid+':'+email))
            existing=db.get(ProjectSalesperson,sid)
            print(f'{"EXISTS" if existing else "ADD"}: {name} · {email} · {phone} · {p.name}')
            if args.apply and not existing:
                db.add(ProjectSalesperson(id=sid, project_id=pid, name=name,
                    role_title='DEMO CONTACT — NOT MONITORED', phone=phone, email=email,
                    active=True, approved=True, updated_at=now()))
                db.add(AuditEvent(id=str(uuid.uuid4()),actor_id='sitepilot-demo-fixture',
                    event='fictional_contact_seeded',subject_id=sid))
        if args.apply:
            db.commit()
            print('Committed. Existing contacts and login accounts left unchanged.')
        else:
            print('DRY RUN: no data changed. Re-run with --apply to insert.')

if __name__=='__main__':main()

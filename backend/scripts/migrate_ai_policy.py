"""Create ONLY the review-flag table; never reset existing SitePilot tables.

Run from backend root after upgrading code:
    python scripts/migrate_ai_policy.py                  # dry run
    python scripts/migrate_ai_policy.py --apply
"""
import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from app.core import engine,ENVIRONMENT
from app.models import AIReviewFlag
from sqlalchemy import inspect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if ENVIRONMENT=='production':raise SystemExit('Refusing migration helper in production; use reviewed Alembic migration instead.')
    if engine.url.drivername.startswith('postgresql'):
        if engine.url.host not in ('localhost','127.0.0.1','::1') or engine.url.database!='sitepilot':
            raise SystemExit('This development helper permits only local PostgreSQL database named sitepilot.')
    elif not engine.url.drivername.startswith('sqlite') or os.getenv('SITEPILOT_TEST_DB')!='1':
        raise SystemExit('Only local PostgreSQL is supported (isolated SQLite test fixture excepted).')
    print('Target:',engine.url.database,'@',engine.url.host,'| table: ai_review_flags')
    print('Will not alter project, lead, booking, user, or message tables.')
    if not args.apply:
        print('DRY RUN: no changes. Use --apply once you have backed up the DB.')
        return
    AIReviewFlag.__table__.create(bind=engine,checkfirst=True)
    assert inspect(engine).has_table('ai_review_flags')
    print('OK: ai_review_flags table exists. No other table was modified.')

if __name__=='__main__':main()

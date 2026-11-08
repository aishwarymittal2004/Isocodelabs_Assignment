"""Local development-only account diagnostics / reset. Never use as a public API.

Run from backend/sitepilot_backend:
  python -m app.sales_account_admin list
  python -m app.sales_account_admin reset-password --email reviewer@example.test
"""
import argparse
import getpass
import os
import sys
from sqlalchemy import select
from .core import SessionLocal, password_hasher
from .models import SalesUser


def main():
    if os.getenv('APP_ENV',os.getenv('ENVIRONMENT','development')).strip().lower() == 'production':
        print('This local repair command is disabled in production.', file=sys.stderr)
        return 1
    parser=argparse.ArgumentParser(description='Inspect/reset local development sales user accounts')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('list',help='Show existing sales account emails (not passwords)')
    reset=sub.add_parser('reset-password',help='Reset one existing local account password')
    reset.add_argument('--email',required=True)
    args=parser.parse_args()
    with SessionLocal() as db:
        if args.command=='list':
            rows=db.scalars(select(SalesUser).order_by(SalesUser.email)).all()
            if not rows:print('No sales accounts found. Run python -m app.seed for your configured demo account.')
            for user in rows:print(f'{user.display_name}: {user.email}')
            return 0
        user=db.scalar(select(SalesUser).where(SalesUser.email==args.email.strip().lower()))
        if not user:
            print('Account not found. Check its email using the list command.',file=sys.stderr)
            return 2
        new=getpass.getpass('New password (12+ characters; input hidden): ')
        confirm=getpass.getpass('Confirm password: ')
        if len(new)<12 or new!=confirm:
            print('Passwords do not match or are shorter than 12 characters.',file=sys.stderr)
            return 2
        user.password_hash=password_hasher.hash(new)
        db.commit()
        print('Password updated for the selected local sales account. Existing JWTs expire normally.')
        return 0

if __name__=='__main__':
    raise SystemExit(main())

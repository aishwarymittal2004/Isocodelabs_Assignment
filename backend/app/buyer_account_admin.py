"""Explicit, local development-only buyer password recovery.

This command is NOT a public password reset API. The operator must independently
verify the buyer's identity before using it. It preserves the existing lead,
bookings, project, and audit records.

Examples (run inside backend/sitepilot_backend):
  python -m app.buyer_account_admin list --project project-1
  python -m app.buyer_account_admin reset-password --project project-1 --phone YOUR_TEST_PHONE --verified-owner

Production password recovery requires verified OTP/email or a controlled human
identity-verification workflow. Never reset solely because someone knows a phone.
"""
import argparse
import getpass
import os
import sys
from sqlalchemy import select
from .core import SessionLocal, password_hasher
from .models import BuyerCredential


def normalize_phone(phone: str) -> str:
    phone = phone.strip()
    return phone if phone.startswith('+') else '+91' + phone if len(phone) == 10 else '+' + phone


def main(argv=None) -> int:
    # Re-check at invocation time so imported modules cannot bypass the guard.
    if os.getenv('APP_ENV', os.getenv('ENVIRONMENT', 'development')).strip().lower() == 'production':
        print('Buyer account repair is disabled in production.', file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description='Local demo buyer account recovery (not a public endpoint)')
    sub = parser.add_subparsers(dest='command', required=True)
    listing = sub.add_parser('list', help='List registered buyer accounts with masked phone numbers')
    listing.add_argument('--project', required=True)
    reset = sub.add_parser('reset-password', help='Update a verified local buyer account password')
    reset.add_argument('--project', required=True)
    reset.add_argument('--phone', required=True)
    reset.add_argument('--verified-owner', action='store_true', help='Confirm ownership was independently verified')
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        if args.command == 'list':
            rows = db.scalars(select(BuyerCredential).where(BuyerCredential.project_id == args.project)).all()
            if not rows:
                print('No registered buyer accounts for the selected project.')
            for row in rows:
                print('Registered buyer: ' + '*' * max(0, len(row.phone) - 4) + row.phone[-4:])
            return 0
        if not args.verified_owner:
            print('Verify the account owner independently, then add --verified-owner.', file=sys.stderr)
            return 2
        credential = db.scalar(select(BuyerCredential).where(
            BuyerCredential.project_id == args.project,
            BuyerCredential.phone == normalize_phone(args.phone),
        ))
        if credential is None:
            print('No matching registered account for that project and phone.', file=sys.stderr)
            return 2
        new_password = getpass.getpass('New password (12+ characters, hidden): ')
        confirmation = getpass.getpass('Confirm password: ')
        if len(new_password) < 12 or new_password != confirmation:
            print('Passwords did not match or were shorter than 12 characters.', file=sys.stderr)
            return 2
        credential.password_hash = password_hasher.hash(new_password)
        db.commit()
        print('Password updated. Existing buyer bookings were not modified.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())

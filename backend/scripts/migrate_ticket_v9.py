"""Explicit additive schema migration; dry-run by default."""
import argparse,sys
from pathlib import Path
from sqlalchemy import inspect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import engine, ENVIRONMENT
from app import models as _existing_models  # register referenced existing tables
from app.tickets_models import BuyerTicket,TicketProject,TicketEvent,TicketNotification

p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
if ENVIRONMENT=='production' or engine.url.database != 'sitepilot' or engine.url.host not in ('localhost','127.0.0.1','::1'):
    raise SystemExit('For safety, this installer only supports the local development PostgreSQL database named sitepilot')
tables=[BuyerTicket.__table__,TicketProject.__table__,TicketEvent.__table__,TicketNotification.__table__]
existing=set(inspect(engine).get_table_names())
missing=[t for t in tables if t.name not in existing]
print('Database:',engine.url.database,'host:',engine.url.host)
print('Missing new ticket tables:',[t.name for t in missing]);print('Existing lead/messages/bookings untouched')
if not args.apply:print('Dry run only. Use --apply after database backup.')
else:
    # SQLAlchemy sorts FK dependencies; this migration never drops a table.
    for t in tables:t.create(bind=engine,checkfirst=True)
    print('OK: Ticket tables ready. Existing tables unchanged.')

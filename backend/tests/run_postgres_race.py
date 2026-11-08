"""Run ONLY against a dedicated, disposable PostgreSQL test database.

PowerShell:
    $env:TEST_DATABASE_URL='postgresql+psycopg://postgres:...@localhost:5432/sitepilot_test'
    python tests/run_postgres_race.py

This script creates tables and seed records in the supplied database; never aim it at
sitepilot or a production database. It intentionally does NOT drop any tables.
"""
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

url = os.environ.get('TEST_DATABASE_URL', '')
if not url.startswith(('postgresql+psycopg://', 'postgresql://')):
    raise SystemExit('Set TEST_DATABASE_URL to a dedicated PostgreSQL test database')
if 'sitepilot_test' not in url.rsplit('/', 1)[-1].split('?', 1)[0]:
    raise SystemExit('Safety guard: database name must contain sitepilot_test')
os.environ['DATABASE_URL'] = url
os.environ['JWT_SECRET'] = 'postgresql-concurrency-test-secret-long-enough'
os.environ.setdefault('DEMO_SALES_PASSWORD', 'test-only-password')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core import Base, engine, SessionLocal
from app.models import Booking
from app.main import app
from app.seed import seed

Base.metadata.create_all(bind=engine)
seed()

# Avoid reliance on test static slots, which could have been booked on a previous run.
from app.models import Slot
from app.core import now
from datetime import timedelta
import uuid

with SessionLocal() as db:
    slot = Slot(id=str(uuid.uuid4()), project_id='project-1',
        starts_at=now()+timedelta(days=9, minutes=int(uuid.uuid4().int % 7000)),
        ends_at=now()+timedelta(days=9, hours=2, minutes=int(uuid.uuid4().int % 7000)), enabled=True)
    # end time must be later than start time
    slot.ends_at = slot.starts_at+timedelta(minutes=45)
    db.add(slot)
    db.commit()
    slot_id = slot.id

client = TestClient(app)
tokens=[]
for n in range(2):
    response=client.post('/api/v1/leads', json={
        'name': f'Race Test {n}', 'phone':f'900000{uuid.uuid4().int % 10000:04d}',
        'project_id':'project-1','source':'website','contact_consent':False
    })
    assert response.status_code == 201, response.text
    tokens.append(response.json()['buyer_session_token'])

barrier=Barrier(2)
def attempt(i):
    barrier.wait(timeout=10)
    return client.post('/api/v1/buyer/bookings', json={'project_id':'project-1','slot_id':slot_id},
        headers={'Authorization':f'Bearer {tokens[i]}','Idempotency-Key':str(uuid.uuid4())}).status_code

with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(attempt,range(2)))
with SessionLocal() as db:
    booked=db.scalars(select(Booking).where(Booking.slot_id==slot_id, Booking.status=='confirmed')).all()
print('Concurrent HTTP results:', results)
print('Confirmed booking count:', len(booked))
assert sorted(results)==[201,409] and len(booked)==1, 'Concurrent reservation invariant FAILED'
print('PASS: exactly one buyer confirmed; no double booking')

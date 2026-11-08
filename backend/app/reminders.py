"""Local demo reminder job: records delivery in a mock outbox, never sends SMS.
Run `python -m app.reminders` to process due reminders. Run under a scheduler
in deployment; one-time CLI execution is not an automatic timer.
"""
from datetime import timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .core import SessionLocal, now
from .models import ReminderOutbox, Booking, Lead, Slot
import uuid

def schedule_reminders(db: Session, booking: Booking, slot: Slot, lead: Lead):
    start=slot.starts_at if slot.starts_at.tzinfo else slot.starts_at.replace(tzinfo=timezone.utc)
    for kind, advance in (("24h",timedelta(hours=24)),("2h",timedelta(hours=2))):
        due=start-advance
        if due<=now():
            continue
        db.add(ReminderOutbox(id=str(uuid.uuid4()),booking_id=booking.id,kind=kind,
                              due_at=due,status='pending' if lead.contact_consent else 'suppressed'))

def suppress_pending(db:Session, booking_id:str):
    for item in db.scalars(select(ReminderOutbox).where(ReminderOutbox.booking_id==booking_id,
                                                 ReminderOutbox.status=='pending')):
        item.status='suppressed'

def run_due(db: Session, current=None):
    current=current or now()
    due=db.scalars(select(ReminderOutbox).where(ReminderOutbox.status=='pending',
                         ReminderOutbox.due_at<=current).order_by(ReminderOutbox.due_at).with_for_update()).all()
    results={'mocked':0,'suppressed':0}
    for item in due:
        booking=db.get(Booking,item.booking_id)
        lead=db.get(Lead,booking.lead_id) if booking else None
        if not booking or booking.status!='confirmed' or not lead or not lead.contact_consent:
            item.status='suppressed';results['suppressed']+=1
        else:
            # No provider is called. Production must replace this with an authorized adapter.
            item.status='mocked';results['mocked']+=1
        item.processed_at=current
    db.commit()
    return results

if __name__=='__main__':
    with SessionLocal() as db:
        print('Mock reminder job:',run_due(db))

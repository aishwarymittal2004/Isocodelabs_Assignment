import os
import uuid
from datetime import timedelta, timezone
from sqlalchemy import select
from .core import Base,engine,SessionLocal,now,password_hasher
from .models import Project,SalesUser,Slot

def seed():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if not db.get(Project,'project-1'):
            db.add(Project(id='project-1',name='Project 1 — Demo',city='Ahmedabad',description='Illustrative project record. Detailed amenities and RERA data awaiting client approval.',price_min_inr=6500000,price_max_inr=12000000,rera_registration=None,facts_approved=True))
            db.add(Project(id='project-2',name='Project 2 — Demo',city='Ahmedabad',description='Illustrative project record. Detailed amenities and RERA data awaiting client approval.',price_min_inr=6500000,price_max_inr=12000000,rera_registration=None,facts_approved=True))
        email=os.getenv('DEMO_SALES_EMAIL','reviewer@example.test')
        password=os.getenv('DEMO_SALES_PASSWORD')
        if password and not db.scalar(select(SalesUser).where(SalesUser.email==email)):
            db.add(SalesUser(id=str(uuid.uuid4()),email=email,password_hash=password_hasher.hash(password),display_name='Demo Sales'))
        # Both projects need genuine future slots, not a fixed date in a mock calendar.
        for project_id in ('project-1','project-2'):
            for day in range(1,15):
                for hour in (5, 7, 9):  # UTC: 10:30, 12:30 and 14:30 IST
                    dt=(now()+timedelta(days=day)).replace(hour=hour,minute=0,second=0,microsecond=0)
                    slot_id=f'demo-{project_id}-{day}-{hour}'
                    if not db.get(Slot,slot_id):
                        db.add(Slot(id=slot_id,project_id=project_id,starts_at=dt,ends_at=dt+timedelta(minutes=45),enabled=True))
        db.commit()
    print('Demo data created. Project descriptions, prices, and time slots are illustrative.')

if __name__=='__main__': seed()

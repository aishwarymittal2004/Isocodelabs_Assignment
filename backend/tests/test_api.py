import importlib
import os
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path}/api.db')
    monkeypatch.setenv('JWT_SECRET','test-only-secret-with-at-least-32-characters')
    monkeypatch.setenv('DEMO_SALES_PASSWORD','test-password')
    monkeypatch.setenv('DEMO_SALES_EMAIL','reviewer@example.test')
    # Isolate authorization tests from the developer's local .env sales-head identity.
    monkeypatch.setenv('SALES_HEAD_EMAIL','reviewer@example.test')
    import app.core,app.models,app.main,app.seed
    importlib.reload(app.core)
    importlib.reload(app.models)
    import app.tickets_models, app.ticket_flow, app.tickets_router
    importlib.reload(app.tickets_models)
    importlib.reload(app.ticket_flow)
    importlib.reload(app.tickets_router)
    importlib.reload(app.main)
    importlib.reload(app.seed)
    app.seed.seed()
    # Offline API tests: simulate missing local model with fallback disabled.
    monkeypatch.setenv('SITEPILOT_ALLOW_CLASSIFIER_FALLBACK', 'false')
    monkeypatch.setenv('SITEPILOT_MODEL_URL', 'https://untrusted.example')
    with TestClient(app.main.app) as c: yield c

def new_buyer(c,phone):
    response=c.post('/api/v1/leads',json={'name':'Demo Buyer','phone':phone,'project_id':'project-1','source':'website','contact_consent':True})
    assert response.status_code==201,response.text
    return response.json()

def bearer(token):return {'Authorization':'Bearer '+token}

def test_signup_login_and_access_isolation(client):
    a=new_buyer(client,'9000000001');b=new_buyer(client,'9000000002')
    assert a['buyer_session_token']!=b['buyer_session_token']
    assert 'possible_duplicate' not in new_buyer(client,'9000000001')
    r=client.post('/api/v1/buyer/conversations/messages',json={'message':'My loan approval is pending.'},headers=bearer(a['buyer_session_token']))
    assert r.status_code==200 and r.json()['ai_status']=='local_policy' and 'loan' in r.json()['reply'].lower()
    assert len(client.get('/api/v1/buyer/conversations/messages',headers=bearer(b['buyer_session_token'])).json())==0
    assert len(client.get('/api/v1/buyer/conversations/messages',headers=bearer(a['buyer_session_token'])).json())==2
    assert client.get('/api/v1/sales/leads',headers=bearer(a['buyer_session_token'])).status_code==403
    assert client.get('/api/v1/buyer/me',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert client.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'}).status_code==200
    assert client.patch('/api/v1/buyer/preferences',json={'contact_consent':False},headers=bearer(a['buyer_session_token'])).json()['contact_consent'] is False

def test_booking_conflicts_idempotency_and_cancellation(client):
    a=new_buyer(client,'9000000003');b=new_buyer(client,'9000000004')
    ah=bearer(a['buyer_session_token'])|{'Idempotency-Key':'same-request-001'}
    bh=bearer(b['buyer_session_token'])|{'Idempotency-Key':'another-request-001'}
    payload={'project_id':'project-1','slot_id':'demo-project-1-2-5'}
    first=client.post('/api/v1/buyer/bookings',json=payload,headers=ah)
    assert first.status_code==201,first.text
    again=client.post('/api/v1/buyer/bookings',json=payload,headers=ah)
    assert again.status_code==201 and again.json()['booking_id']==first.json()['booking_id']
    conflict=client.post('/api/v1/buyer/bookings',json=payload,headers=bh)
    assert conflict.status_code==409,conflict.text
    assert client.get('/api/v1/buyer/bookings',headers=bearer(b['buyer_session_token'])).json()==[]
    assert client.post('/api/v1/buyer/bookings/'+first.json()['booking_id']+'/cancel',headers=bearer(b['buyer_session_token'])).status_code==404
    assert client.post('/api/v1/buyer/bookings/'+first.json()['booking_id']+'/cancel',headers=bearer(a['buyer_session_token'])).json()['status']=='cancelled'
    assert client.post('/api/v1/buyer/bookings',json=payload,headers=bh).status_code==201

def test_invalid_requests_and_project_scope(client):
    r=client.post('/api/v1/leads',json={'name':'X','phone':'abc','project_id':'project-1','source':'website'})
    assert r.status_code==422
    a=new_buyer(client,'9000000005')
    h=bearer(a['buyer_session_token'])
    assert client.get('/api/v1/projects/project-2/slots?date=2026-11-07').status_code==200
    assert client.post('/api/v1/buyer/bookings',json={'project_id':'project-2','slot_id':'demo-project-1-2-5'},headers=h|{'Idempotency-Key':'different-request'}).status_code==403


def test_handoff_and_duplicate_review(client):
    a=new_buyer(client,'9000000006')
    new_buyer(client,'9000000006')
    assert client.post('/api/v1/buyer/handoff',headers=bearer(a['buyer_session_token'])).status_code==202
    auth=client.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'}).json()
    headers=bearer(auth['access_token'])
    assert any(l['lead_id']==a['lead_id'] for l in client.get('/api/v1/sales/handoffs',headers=headers).json())
    duplicates=client.get('/api/v1/sales/leads/duplicates',headers=headers)
    assert duplicates.status_code==200 and len(duplicates.json()[0]['candidates'])==2
    assert '9000000006' not in str(duplicates.json())


def test_public_availability_and_both_projects(client):
    from datetime import datetime, timezone, timedelta
    for project_id in ('project-1', 'project-2'):
        # Seeded future slots are discoverable without buyer identity.
        date=(datetime.now(timezone.utc)+timedelta(days=2)).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date().isoformat()
        response=client.get(f'/api/v1/projects/{project_id}/slots',params={'date':date})
        assert response.status_code==200,response.text
        assert response.json()['project_id']==project_id
        assert isinstance(response.json()['slots'],list)
    assert client.get('/api/v1/projects/missing/slots',params={'date':date}).status_code==404

def test_live_sales_workspace_requires_auth_and_uses_real_rows(client):
    buyer=new_buyer(client,'9000000077')
    lead_id=buyer['lead_id']
    private=['/api/v1/sales/dashboard/overview','/api/v1/sales/leads/'+lead_id+'/messages','/api/v1/sales/users']
    for url in private:
        assert client.get(url).status_code==401
    token=client.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'}).json()['access_token']
    auth=bearer(token)
    leads=client.get('/api/v1/sales/leads',headers=auth)
    assert leads.status_code==200 and any(l['lead_id']==lead_id for l in leads.json())
    overview=client.get('/api/v1/sales/dashboard/overview',headers=auth)
    assert overview.status_code==200
    assert overview.json()['leads_total']>=1
    assert overview.json()['sources'][0]['leads']>=1
    assert client.get('/api/v1/sales/leads/'+lead_id+'/messages',headers=auth).json()==[]
    users=client.get('/api/v1/sales/users',headers=auth).json()
    assert users
    assigned=client.patch('/api/v1/sales/leads/'+lead_id+'/assign',headers=auth,json={'user_id':users[0]['id']})
    assert assigned.status_code==200 and assigned.json()['assigned_user_id']==users[0]['id']
    assert client.patch('/api/v1/sales/leads/'+lead_id+'/assign',headers=auth,json={'user_id':'invalid'}).status_code==422
    assert client.patch('/api/v1/sales/leads/'+lead_id+'/assign',headers=bearer(buyer['buyer_session_token']),json={'user_id':users[0]['id']}).status_code==403

def test_visit_attendance_prevents_early_or_unauthorized_marking(client):
    buyer=new_buyer(client,'9000000088')
    book=client.post('/api/v1/buyer/bookings',headers=bearer(buyer['buyer_session_token'])|{'Idempotency-Key':'sales-visit-88'},json={'project_id':'project-1','slot_id':'demo-project-1-2-5'})
    assert book.status_code==201
    ref=book.json()['booking_id']
    auth=bearer(client.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'}).json()['access_token'])
    assert client.patch('/api/v1/sales/bookings/'+ref+'/attendance',headers=auth,json={'status':'invalid'}).status_code==422
    assert client.patch('/api/v1/sales/bookings/'+ref+'/attendance',headers=auth,json={'status':'attended'}).status_code==409
    assert client.patch('/api/v1/sales/bookings/'+ref+'/attendance',headers=bearer(buyer['buyer_session_token']),json={'status':'no_show'}).status_code==403

def test_fact_review_is_persistent_approved_only_and_authorized(client):
    import app.core as core
    from app.models import SalesUser
    token=client.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'}).json()['access_token']
    auth=bearer(token)
    p='/api/v1/sales/projects/project-1/facts'
    proposal=client.post(p,json={'key':'parking_policy','value':'Parking details available upon request.'},headers=auth)
    assert proposal.status_code==201,proposal.text
    ref=proposal.json()['id']
    assert client.get('/api/v1/projects/project-1/facts').json()['facts']==[]
    assert client.get(p,headers=auth).json()['history'][0]['status']=='pending'
    assert client.post('/api/v1/sales/facts/'+ref+'/review',json={'action':'approve'}).status_code==401
    with core.SessionLocal() as db:
        u=SalesUser(id='other-sales',email='other@example.test',password_hash='test',display_name='Other')
        db.add(u);db.commit()
    other=bearer(core.make_token('other-sales','sales'))
    assert client.post('/api/v1/sales/facts/'+ref+'/review',json={'action':'approve'},headers=other).status_code==403
    assert client.post('/api/v1/sales/facts/'+ref+'/review',json={'action':'approve'},headers=auth).status_code==200
    assert client.post('/api/v1/sales/facts/'+ref+'/review',json={'action':'approve'},headers=auth).status_code==409
    published=client.get('/api/v1/projects/project-1/facts').json()['facts']
    assert published[0]['value']=='Parking details available upon request.'
    second=client.post(p,json={'key':'parking_policy','value':'Edited claim pending review.'},headers=other)
    assert second.status_code==201
    assert client.get('/api/v1/projects/project-1/facts').json()['facts'][0]['value']==published[0]['value']
    assert client.post('/api/v1/sales/facts/'+second.json()['id']+'/review',json={'action':'reject'},headers=auth).status_code==200
    assert client.get('/api/v1/projects/project-1/facts').json()['facts'][0]['value']==published[0]['value']

def test_reminders_obey_consent_and_cancel(client):
    from datetime import timedelta
    import app.core as core
    from app.models import ReminderOutbox
    from app.reminders import run_due
    a=new_buyer(client,'9000019001')
    auth=bearer(a['buyer_session_token'])
    booking=client.post('/api/v1/buyer/bookings',headers=auth|{'Idempotency-Key':'reminder-test-1'},json={'project_id':'project-1','slot_id':'demo-project-1-4-5'})
    assert booking.status_code==201,booking.text
    token=client.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'}).json()['access_token']
    reminders=client.get('/api/v1/sales/reminders',headers=bearer(token)).json()
    assert len(reminders)==2 and all(x['status']=='pending' for x in reminders)
    with core.SessionLocal() as db:
        for item in db.query(ReminderOutbox):item.due_at=core.now()-timedelta(minutes=3)
        db.commit()
        results=run_due(db)
        assert results['mocked']==2
    assert all(x['status']=='mocked' for x in client.get('/api/v1/sales/reminders',headers=bearer(token)).json())
    b=new_buyer(client,'9000019002')
    bh=bearer(b['buyer_session_token'])
    second=client.post('/api/v1/buyer/bookings',headers=bh|{'Idempotency-Key':'reminder-test-2'},json={'project_id':'project-1','slot_id':'demo-project-1-5-5'})
    assert second.status_code==201
    assert client.patch('/api/v1/buyer/preferences',json={'contact_consent':False},headers=bh).status_code==200
    remaining=client.get('/api/v1/sales/reminders',headers=bearer(token)).json()
    assert all(x['status']=='suppressed' for x in remaining if x['booking_id']==second.json()['booking_id'])
    assert client.post('/api/v1/buyer/bookings/'+second.json()['booking_id']+'/cancel',headers=bh).status_code==200

def test_sales_head_slot_controls(client):
    import app.core as core
    token=client.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'}).json()['access_token']
    head=bearer(token)
    slots=client.get('/api/v1/sales/projects/project-1/slots',headers=head)
    assert slots.status_code==200
    slot=slots.json()[0]['slot_id']
    no_auth=client.patch('/api/v1/sales/slots/'+slot,json={'enabled':False})
    assert no_auth.status_code==401
    assert client.patch('/api/v1/sales/slots/'+slot,json={'enabled':False},headers=head).json()['enabled'] is False
    assert client.patch('/api/v1/sales/slots/'+slot,json={'enabled':True},headers=head).json()['enabled'] is True
    buyer=new_buyer(client,'9000019003')
    booked=client.post('/api/v1/buyer/bookings',headers=bearer(buyer['buyer_session_token'])|{'Idempotency-Key':'slot-test-1'},json={'project_id':'project-1','slot_id':slot})
    assert booked.status_code==201
    assert client.patch('/api/v1/sales/slots/'+slot,json={'enabled':False},headers=head).status_code==409

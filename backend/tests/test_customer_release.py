"""Buyer account, drafts, and handoff acceptance tests — no external Ollama call."""
import importlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path}/customer.db')
    monkeypatch.setenv('JWT_SECRET', 'test-only-secret-with-at-least-32-characters')
    monkeypatch.setenv('DEMO_SALES_EMAIL','reviewer@example.test')
    monkeypatch.setenv('DEMO_SALES_PASSWORD','test-password')
    monkeypatch.setenv('SALES_HEAD_EMAIL','reviewer@example.test')
    monkeypatch.setenv('SITEPILOT_MODEL_URL','https://untrusted.example')
    monkeypatch.setenv('SITEPILOT_ALLOW_CLASSIFIER_FALLBACK','false')
    import app.core, app.models, app.main, app.seed
    importlib.reload(app.core)
    importlib.reload(app.models)
    import app.tickets_models, app.ticket_flow, app.tickets_router
    importlib.reload(app.tickets_models)
    importlib.reload(app.ticket_flow)
    importlib.reload(app.tickets_router)
    importlib.reload(app.main)
    importlib.reload(app.seed)
    app.seed.seed()
    with TestClient(app.main.app) as c:
        yield c

def bearer(token):return {'Authorization':'Bearer '+token}
def register(client,phone,project='project-1'):
    data={'name':'Test Buyer','phone':phone,'project_id':project,'password':'a-strong-password-123','contact_consent':False}
    response=client.post('/api/v1/buyer/auth/register',json=data)
    assert response.status_code==201,response.text
    return response.json()

def test_buyer_can_sign_in_after_booking_and_cancel_but_not_someone_elses(client):
    a=register(client,'9000000391');b=register(client,'9000000392')
    slot='demo-project-1-2-5'
    first=client.post('/api/v1/buyer/bookings',json={'slot_id':slot,'project_id':'project-1'},
                      headers={**bearer(a['buyer_session_token']),'Idempotency-Key':'login-booking-001'})
    assert first.status_code==201,first.text
    assert client.post('/api/v1/buyer/bookings/'+first.json()['booking_id']+'/cancel',
                       headers=bearer(b['buyer_session_token'])).status_code==404
    assert client.post('/api/v1/buyer/auth/login',json={'phone':'9000000391','password':'wrong','project_id':'project-1'}).status_code==401
    signed=client.post('/api/v1/buyer/auth/login',json={'phone':'9000000391','password':'a-strong-password-123','project_id':'project-1'})
    assert signed.status_code==200
    token=signed.json()['buyer_session_token']
    assert len(client.get('/api/v1/buyer/bookings',headers=bearer(token)).json())==1
    assert client.post('/api/v1/buyer/bookings/'+first.json()['booking_id']+'/cancel',headers=bearer(token)).json()['status']=='cancelled'
    assert client.get('/api/v1/buyer/bookings',headers=bearer(token)).json()[0]['status']=='cancelled'

def test_duplicate_registration_does_not_grant_access(client):
    register(client,'9000000393')
    second=client.post('/api/v1/buyer/auth/register',json={'name':'Someone Else','phone':'9000000393',
        'project_id':'project-1','password':'different-pass-123','contact_consent':True})
    assert second.status_code==409
    assert 'buyer_session_token' not in second.text
    assert client.post('/api/v1/buyer/auth/login',json={'phone':'9000000393','password':'different-pass-123','project_id':'project-1'}).status_code==401

def test_legacy_buyer_session_can_be_secured_but_not_claimed_again(client):
    lead=client.post('/api/v1/leads',json={'name':'Early Buyer','phone':'9000000394','project_id':'project-1','source':'website','contact_consent':False}).json()
    token=lead['buyer_session_token']
    assert client.post('/api/v1/buyer/auth/claim',json={'password':'my-private-pass-123'},headers=bearer(token)).status_code==201
    assert client.post('/api/v1/buyer/auth/claim',json={'password':'other-private-pass'},headers=bearer(token)).status_code==409
    assert client.post('/api/v1/buyer/auth/login',json={'phone':'9000000394','password':'my-private-pass-123','project_id':'project-1'}).status_code==200

def test_new_sales_project_stays_private_until_head_approval(client):
    import app.core as core
    from app.models import SalesUser
    with core.SessionLocal() as db:
        db.add(SalesUser(id='exec1',email='exec1@example.test',password_hash='dummy',display_name='Executive'))
        db.commit()
    token=core.make_token('exec1','sales')
    sales=bearer(token)
    created=client.post('/api/v1/sales/projects',json={'name':'New Green Heights','city':'Ahmedabad','description':'Draft details for sales-head review'},headers=sales)
    assert created.status_code==201,created.text
    project_id=created.json()['id']
    assert created.json()['published'] is False
    assert project_id not in [p['id'] for p in client.get('/api/v1/projects').json()]
    assert client.get('/api/v1/projects/'+project_id).status_code==404
    assert client.patch(f'/api/v1/sales/projects/{project_id}/publication',json={'publish':True},headers=sales).status_code==403
    headtoken=client.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'}).json()['access_token']
    head=bearer(headtoken)
    assert client.patch(f'/api/v1/sales/projects/{project_id}/publication',json={'publish':True},headers=head).status_code==409
    for key,value in [('rera_registration','Registration verified in developer source'),('configuration','2 and 3 BHK published in approved sheet')]:
        proposal=client.post(f'/api/v1/sales/projects/{project_id}/facts',json={'key':key,'value':value},headers=sales)
        assert proposal.status_code==201,proposal.text
        approved=client.post(f"/api/v1/sales/facts/{proposal.json()['id']}/review",json={'action':'approve'},headers=head)
        assert approved.status_code==200,approved.text
    published=client.patch(f'/api/v1/sales/projects/{project_id}/publication',json={'publish':True},headers=head)
    assert published.status_code==200,published.text
    assert project_id in [p['id'] for p in client.get('/api/v1/projects').json()]
    assert client.get('/api/v1/projects/'+project_id+'/facts').json()['facts']

def test_handoff_acknowledges_request_and_sales_can_claim(client):
    registered=register(client,'9000000395');buyer_auth=bearer(registered['buyer_session_token'])
    result=client.post('/api/v1/buyer/handoff',headers=buyer_auth)
    assert result.status_code==202
    assert 'sales team queue' in result.json()['message']
    before=client.get('/api/v1/buyer/handoff',headers=buyer_auth).json()
    assert before['assigned'] is False
    headtoken=client.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'}).json()['access_token']
    lead_id=registered['lead_id']
    accepted=client.post(f'/api/v1/sales/leads/{lead_id}/handoff/accept',headers=bearer(headtoken))
    assert accepted.status_code==200
    assert client.get('/api/v1/buyer/handoff',headers=buyer_auth).json()['assigned'] is True
    assert client.post(f'/api/v1/sales/leads/{lead_id}/handoff/accept',headers=buyer_auth).status_code==403

def test_fast_routes_no_inference_for_verified_facts_and_booking(client,monkeypatch):
    import app.main as main
    registered=register(client,'9000000396')
    auth=bearer(registered['buyer_session_token'])
    def not_called(*_):raise AssertionError('Ollama classification should not run for explicit facts or booking')
    monkeypatch.setattr(main,'decide',not_called)
    for message in ['What project details are verified?', 'I would like to book a site visit.']:
        response=client.post('/api/v1/buyer/conversations/messages',headers=auth,json={'message':message,'language':'en'})
        assert response.status_code==200,response.text
        assert response.json()['reply_strategy']=='server_controlled'
        assert response.json()['ai_status']=='local_policy'
        assert isinstance(response.json()['latency_ms'],int)

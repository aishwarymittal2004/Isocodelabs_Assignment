"""V9 single-ticket, first-claim, privacy, and AI shutdown regression tests."""
from test_api import client,new_buyer,bearer
from app.core import now


def login(c):
    r=c.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'})
    assert r.status_code==200,r.text
    return bearer(r.json()['access_token'])


def test_ticket_one_conversation_across_projects_and_export(client):
    a=new_buyer(client,'9000099010');h=bearer(a['buyer_session_token'])
    t=client.get('/api/v1/buyer/ticket',headers=h)
    assert t.status_code==200,t.text
    ref=t.json()['reference']
    assert t.json()['project_ids']==['project-1']
    first=client.post('/api/v1/buyer/ticket/projects',headers=h,json={'project_id':'project-2'})
    assert first.status_code==200,first.text
    assert set(first.json()['project_ids'])=={'project-1','project-2'}
    again=client.post('/api/v1/buyer/ticket/projects',headers=h,json={'project_id':'project-2'})
    assert again.status_code==200
    assert again.json()['reference']==ref
    assert len(again.json()['project_ids'])==2
    assert client.post('/api/v1/buyer/ticket/projects',headers=h,json={'project_id':'missing'}).status_code==404
    result=client.get('/api/v1/buyer/ticket/projects',headers=h)
    assert result.status_code==200
    assert result.json()['source']=='approved_revisions_only'
    assert all(project['facts']=={} for project in result.json()['projects'])
    exported=client.get('/api/v1/buyer/ticket/export',headers=h)
    assert exported.status_code==200 and ref in exported.text
    assert client.get('/api/v1/buyer/ticket/export').status_code==401


def test_requirements_and_missing_comparison_flag_same_ticket(client):
    a=new_buyer(client,'9000099011');h=bearer(a['buyer_session_token'])
    result=client.post('/api/v1/buyer/conversations/messages',headers=h,json={
        'message':'Can you recommend other properties? I need 2BHK near a hospital, within a budget of 5 lakhs.','language':'en'})
    assert result.status_code==200,result.text
    reply=result.json()['reply']
    assert '2 BHK' in reply
    assert '₹500,000' in reply
    assert 'cannot verify school, hospital, or transport proximity' in reply.lower()
    assert 'insufficient approved information' in reply.lower()
    ticket=client.get('/api/v1/buyer/ticket',headers=h).json()
    assert ticket['status']=='pending'
    assert ticket['requirements']['configuration']=='2 BHK'
    assert ticket['requirements']['budget_inr']==500000
    assert ticket['requirements']['hospital_priority'] is True
    assert client.get('/api/v1/buyer/ticket/history',headers=h).json()['reference']==ticket['reference']


def test_first_acceptance_only_and_ai_stops_and_human_replies(client):
    a=new_buyer(client,'9000099012');h=bearer(a['buyer_session_token'])
    client.post('/api/v1/buyer/handoff',headers=h)
    t=client.get('/api/v1/buyer/ticket',headers=h).json()
    assert t['status']=='pending'
    sh=login(client)
    queue=client.get('/api/v1/sales/tickets/queue',headers=sh)
    assert queue.status_code==200
    assert any(row['id']==t['id'] for row in queue.json())
    accepted=client.post(f"/api/v1/sales/tickets/{t['id']}/accept",headers=sh)
    assert accepted.status_code==200,accepted.text
    assert accepted.json()['status']=='accepted'
    assert client.post(f"/api/v1/sales/tickets/{t['id']}/accept",headers=sh).status_code==409
    # Old assignment route cannot override accepted ticket.
    from app.core import SessionLocal
    from app.models import SalesUser
    with SessionLocal() as db:
        user=db.query(SalesUser).filter(SalesUser.email=='reviewer@example.test').first()
        owner_id=user.id
    assert client.patch(f"/api/v1/sales/leads/{a['lead_id']}/assign",headers=sh,json={'user_id':owner_id}).status_code==409
    ask=client.post('/api/v1/buyer/conversations/messages',headers=h,json={'message':'What is the final price?','language':'en'})
    assert ask.status_code==200,ask.text
    assert ask.json()['reply'] is None
    assert ask.json()['ai_status']=='human_takeover'
    response=client.post(f"/api/v1/sales/tickets/{t['id']}/messages",headers=sh,json={'message':'I will confirm the approved information.'})
    assert response.status_code==201,response.text
    history=client.get('/api/v1/buyer/ticket/history',headers=h).json()['entries']
    assert any(e.get('speaker')=='buyer' and e['text']=='What is the final price?' for e in history)
    assert any(e.get('speaker')=='sales' for e in history)
    resolved=client.post(f"/api/v1/sales/tickets/{t['id']}/resolve",headers=sh,json={'note':'Buyer contacted; enquiry closed.'})
    assert resolved.status_code==200
    assert resolved.json()['status']=='resolved'
    assert client.post('/api/v1/buyer/conversations/messages',headers=h,json={'message':'Hello','language':'en'}).json()['ai_status']=='human_takeover'


def test_sales_privacy_and_auth(client):
    a=new_buyer(client,'9000099013');h=bearer(a['buyer_session_token'])
    t=client.get('/api/v1/buyer/ticket',headers=h).json()
    assert client.get('/api/v1/sales/tickets/queue').status_code==401
    assert client.get(f"/api/v1/sales/tickets/{t['id']}",headers=h).status_code==403
    assert client.get('/api/v1/buyer/ticket').status_code==401
    # Only a real authenticated salesperson can claim a queued ticket.
    assert client.post(f"/api/v1/sales/tickets/{t['id']}/accept",headers=h).status_code==403


def test_approved_project_comparison_never_leaks_pending_facts(client):
    a=new_buyer(client,'9000099014');auth=bearer(a['buyer_session_token']);sales=login(client)
    assert client.post('/api/v1/buyer/ticket/projects',headers=auth,json={'project_id':'project-2'}).status_code==200
    for project_id,parking in [('project-1','One verified space'),('project-2','Two verified spaces')]:
        p=client.post(f'/api/v1/sales/projects/{project_id}/facts',headers=sales,
                      json={'key':'parking_policy','value':parking})
        assert p.status_code==201,p.text
        approved=client.post('/api/v1/sales/facts/'+p.json()['id']+'/review',headers=sales,json={'action':'approve'})
        assert approved.status_code==200,approved.text
    pending=client.post('/api/v1/sales/projects/project-1/facts',headers=sales,
                        json={'key':'final_discount','value':'INVENTED DISCOUNT SHOULD NEVER LEAK'})
    assert pending.status_code==201
    r=client.post('/api/v1/buyer/conversations/messages',headers=auth,
                 json={'message':'Compare these two projects please','language':'en'})
    assert r.status_code==200,r.text
    assert 'One verified space' in r.json()['reply']
    assert 'Two verified spaces' in r.json()['reply']
    assert 'INVENTED DISCOUNT SHOULD NEVER LEAK' not in r.json()['reply']
    public=client.get('/api/v1/buyer/ticket/projects',headers=auth)
    assert public.status_code==200
    assert 'INVENTED DISCOUNT SHOULD NEVER LEAK' not in public.text

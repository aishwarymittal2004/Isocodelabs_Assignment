"""Non-negotiable SitePilot agent policy and sales-head workflow tests."""
from test_api import client, new_buyer, bearer


def sales_token(c):
    r=c.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'})
    assert r.status_code==200,r.text
    return bearer(r.json()['access_token'])


def send(c,token,message):
    r=c.post('/api/v1/buyer/conversations/messages',json={'message':message,'language':'en'},headers=bearer(token))
    assert r.status_code==200,r.text
    return r.json()


def test_missing_fact_auto_handoff_and_daily_review(client):
    a=new_buyer(client,'9000020001')
    response=send(client,a['buyer_session_token'],'What are the maintenance charges?')
    assert response['handoff_requested'] is True
    assert response['review_flagged'] is True
    assert response['fact_resolution']=='missing_fact_escalated'
    assert 'recorded a request' in response['reply'].lower()
    lead=client.get('/api/v1/buyer/me',headers=bearer(a['buyer_session_token'])).json()
    assert lead['status']=='handoff_requested'
    assert client.get('/api/v1/sales/ai-review').status_code==401
    q=client.get('/api/v1/sales/ai-review',headers=sales_token(client))
    assert q.status_code==200,q.text
    items=q.json()['items']
    match=next(x for x in items if x['lead_id']==a['lead_id'])
    assert match['reason']=='missing_approved_fact'
    assert match['status']=='open'
    assert client.post(f'/api/v1/sales/ai-review/{match["id"]}/review',json={'note':'Checked fact sheet; assigned to sales.'}).status_code==401
    reviewed=client.post(f'/api/v1/sales/ai-review/{match["id"]}/review',
        headers=sales_token(client),json={'note':'Checked fact sheet; assigned to sales.'})
    assert reviewed.status_code==200,reviewed.text
    assert client.get('/api/v1/sales/ai-review',headers=sales_token(client)).json()['items']==[]
    assert client.post(f'/api/v1/sales/ai-review/{match["id"]}/review',
        headers=sales_token(client),json={'note':'Already done'}).status_code==409


def test_direct_human_intent_auto_handoff(client):
    a=new_buyer(client,'9000020002')
    r=send(client,a['buyer_session_token'],'I want to talk to a salesperson.')
    assert r['handoff_requested'] is True
    assert r['reply_strategy']=='server_controlled'
    assert 'recorded' in r['reply'].lower()
    rows=client.get('/api/v1/sales/ai-review',headers=sales_token(client)).json()['items']
    assert rows[0]['reason']=='human_requested'


def test_final_quote_not_generated_and_requests_human(client):
    a=new_buyer(client,'9000020003')
    r=send(client,a['buyer_session_token'],'Can I get the final price and a discount?')
    assert r['handoff_requested'] is True
    assert r['review_flagged'] is True
    assert 'cannot provide a final price' in r['reply'].lower()
    assert '₹' not in r['reply']


def test_approved_fact_retrieval_and_no_unapproved_fact_leak(client):
    a=new_buyer(client,'9000020004')
    admin=sales_token(client)
    project='project-1'
    proposed=client.post(f'/api/v1/sales/projects/{project}/facts',headers=admin,
        json={'key':'parking','value':'Parking includes one space per unit.'})
    assert proposed.status_code==201,proposed.text
    # Pending facts are never shown to buyers or AI.
    r=send(client,a['buyer_session_token'],'What parking is available?')
    assert 'one space per unit' not in r['reply'].lower()
    assert r['handoff_requested'] is True
    review=client.post(f'/api/v1/sales/facts/{proposed.json()["id"]}/review',headers=admin,json={'action':'approve'})
    assert review.status_code==200,review.text
    fresh=new_buyer(client,'9000020005')
    response=send(client,fresh['buyer_session_token'],'What parking is available?')
    assert response['handoff_requested'] is False
    assert 'one space per unit' in response['reply'].lower()
    assert 'approved' in response['reply'].lower()


def test_booking_tool_requires_explicit_confirmation(client):
    a=new_buyer(client,'9000020006')
    auth=bearer(a['buyer_session_token'])
    r=send(client,a['buyer_session_token'],'Show me site visit times.')
    assert r['confirmation_required'] is True
    assert r['booking_options']
    assert client.get('/api/v1/buyer/bookings',headers=auth).json()==[]
    # Only explicit POST /bookings can commit appointment.
    chosen=r['booking_options'][0]
    confirmed=client.post('/api/v1/buyer/bookings',headers=auth|{'Idempotency-Key':'explicit-confirmation-2026'},
        json={'project_id':chosen['project_id'],'slot_id':chosen['slot_id']})
    assert confirmed.status_code==201,confirmed.text


def test_sales_head_only_review(client):
    from app.models import SalesUser
    from app import core
    a=new_buyer(client,'9000020007')
    send(client,a['buyer_session_token'],'I want to talk to a person')
    with core.SessionLocal() as db:
        db.add(SalesUser(id='sales-trainee',email='trainee@example.test',password_hash='irrelevant',display_name='Trainee'))
        db.commit()
    token=bearer(core.make_token('sales-trainee','sales'))
    assert client.get('/api/v1/sales/ai-review',headers=token).status_code==403


def test_handoff_button_creates_review_flag_once(client):
    a=new_buyer(client,'9000020008')
    h=bearer(a['buyer_session_token'])
    first=client.post('/api/v1/buyer/handoff',headers=h)
    assert first.status_code==202,first.text
    again=client.post('/api/v1/buyer/handoff',headers=h)
    assert again.status_code==202,again.text
    q=client.get('/api/v1/sales/ai-review',headers=sales_token(client))
    assert q.status_code==200,q.text
    matches=[x for x in q.json()['items'] if x['lead_id']==a['lead_id']]
    assert len(matches)==1
    assert matches[0]['reason']=='human_requested'
    assert 'handoff button' in matches[0]['source_message']

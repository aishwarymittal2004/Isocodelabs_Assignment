from test_api import new_buyer, bearer, client
from app.agent import AgentDecision


def test_agent_booking_options_and_explicit_confirmation(client, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, 'decide', lambda *args: (AgentDecision(
        intent='booking', concern_type='none', evidence_kind='unknown',
        evidence_quote='', reply='I booked your appointment.', needs_human=False), 'local_model'))
    a = new_buyer(client, '9000010011')
    b = new_buyer(client, '9000010012')
    ah = bearer(a['buyer_session_token'])
    bh = bearer(b['buyer_session_token'])
    r = client.post('/api/v1/buyer/conversations/messages', headers=ah,
                    json={'message':'I want to book a site visit.', 'language':'en'})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['confirmation_required'] is True
    assert body['booking_options']
    assert 'I booked your appointment' not in body['reply']
    assert client.get('/api/v1/buyer/bookings', headers=ah).json() == []
    chosen = body['booking_options'][0]
    assert chosen['project_id'] == 'project-1'
    booking = client.post('/api/v1/buyer/bookings', headers=ah | {'Idempotency-Key':'agent-booking-001'},
                          json={'project_id':'project-1','slot_id':chosen['slot_id']})
    assert booking.status_code == 201, booking.text
    assert len(client.get('/api/v1/buyer/bookings',headers=ah).json()) == 1
    assert client.post('/api/v1/buyer/bookings', headers=bh | {'Idempotency-Key':'agent-booking-002'},
                       json={'project_id':'project-1','slot_id':chosen['slot_id']}).status_code == 409
    slots = client.get('/api/v1/buyer/assistant/booking-options', headers=bh)
    assert slots.status_code == 200
    assert chosen['slot_id'] not in [s['slot_id'] for s in slots.json()['slots']]
    assert client.get('/api/v1/buyer/assistant/booking-options').status_code == 401
    assert client.get('/api/v1/buyer/assistant/booking-options', headers={'Authorization':'Bearer invalid'}).status_code == 401


def test_agent_never_shows_other_project_options(client, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, 'decide', lambda *args: (AgentDecision(
        intent='booking',concern_type='none',evidence_kind='unknown',evidence_quote='',
        reply='OK', needs_human=False), 'local_model'))
    lead = client.post('/api/v1/leads',json={'name':'Other Buyer','phone':'9000010021',
           'project_id':'project-2','source':'website'}).json()
    res = client.post('/api/v1/buyer/conversations/messages', headers=bearer(lead['buyer_session_token']),
                      json={'message':'I want to book a visit'}).json()
    assert all(s['project_id']=='project-2' for s in res['booking_options'])

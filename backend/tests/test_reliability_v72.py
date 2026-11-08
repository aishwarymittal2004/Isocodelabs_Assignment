"""Regression coverage for the repeated buyer-facing failures seen in V7.1."""
from test_api import client, bearer
from app.agent import AgentDecision, fast_route, is_budget_concern, is_price_question, safe_response
from app.conversation import eligible_for_contextual_reply
from types import SimpleNamespace


def test_short_budget_followup_is_not_generic_even_when_model_offline(client, monkeypatch):
    import app.main as main
    token = client.post('/api/v1/buyer/auth/register', json={
        'name': 'Example Buyer', 'phone': '9000000801', 'project_id': 'project-1',
        'password': 'demo-example-pass-123', 'contact_consent': False,
    }).json()['buyer_session_token']
    # This must not depend on contacting Ollama.
    monkeypatch.setattr(main, 'decide', lambda *_: (_ for _ in ()).throw(AssertionError('Ollama should not run')))
    first = client.post('/api/v1/buyer/conversations/messages', headers=bearer(token), json={
        'message': 'My wife is not happy with the property', 'language': 'en',
    })
    assert first.status_code == 200, first.text
    second = client.post('/api/v1/buyer/conversations/messages', headers=bearer(token), json={
        'message': 'She is concerned about cost', 'language': 'en',
    })
    assert second.status_code == 200, second.text
    body = second.json()
    assert body['reply_strategy'] == 'server_controlled'
    assert body['hesitation']['category'] == 'budget'
    assert body['hesitation']['evidence'] == 'She is concerned about cost'
    assert 'cost' in body['reply'].lower()
    assert 'approved' in body['reply'].lower()
    assert 'what would you like to explore' not in body['reply'].lower()
    assert body['build'] == 'sitepilot-reliability-v7.2'


def test_price_question_goes_to_approved_facts_and_budget_worry_does_not():
    for text in ['She is concerned about cost','The flat is too expensive','Price is a concern for my wife']:
        assert is_budget_concern(text)
        d = fast_route(text)
        assert d and d.intent == 'hesitation' and d.concern_type == 'budget'
        assert not eligible_for_contextual_reply(d, text)
    for text in ['What is the price?','How much does the apartment cost?']:
        assert not is_budget_concern(text)
        assert fast_route(text).intent == 'project_facts'
    p=SimpleNamespace(name='Demo',city='Ahmedabad',price_min_inr=6500000,price_max_inr=8000000)
    reply, grounding = safe_response(fast_route('What is the price?'), 'What is the price?',p,facts={})
    assert '65,00,000' not in reply and grounding == 'limited_verified_facts'


def test_duplicate_account_preserves_booking_and_old_password(client):
    data={'name':'Original Buyer','phone':'9000000802','project_id':'project-1','password':'original-good-pass-123','contact_consent':False}
    first=client.post('/api/v1/buyer/auth/register',json=data)
    assert first.status_code==201
    token=first.json()['buyer_session_token']
    slot='demo-project-1-2-5'
    booked=client.post('/api/v1/buyer/bookings',json={'project_id':'project-1','slot_id':slot},headers={**bearer(token),'Idempotency-Key':'existing-account-v72'})
    assert booked.status_code==201,booked.text
    second=client.post('/api/v1/buyer/auth/register',json={**data,'password':'different-long-password-123'})
    assert second.status_code==409
    assert 'buyer_session_token' not in second.text
    assert client.post('/api/v1/buyer/auth/login',json={**data,'password':'different-long-password-123'}).status_code==401
    signed=client.post('/api/v1/buyer/auth/login',json={'project_id':'project-1','phone':'9000000802','password':data['password']})
    assert signed.status_code==200
    visits=client.get('/api/v1/buyer/bookings',headers=bearer(signed.json()['buyer_session_token']))
    assert visits.status_code==200 and any(b['booking_id']==booked.json()['booking_id'] for b in visits.json())


def test_development_only_buyer_password_reset_requires_verification(client,monkeypatch,capsys):
    from app import buyer_account_admin
    phone='9000000803'
    data={'name':'Example','phone':phone,'project_id':'project-1','password':'original-good-pass-123','contact_consent':False}
    assert client.post('/api/v1/buyer/auth/register',json=data).status_code==201
    def try_reset(extra=()):
        return buyer_account_admin.main(['reset-password','--project','project-1','--phone',phone,*extra])
    assert try_reset()==2
    monkeypatch.setattr(buyer_account_admin.getpass,'getpass',lambda _: 'replacement-good-pass-123')
    assert try_reset(('--verified-owner',))==0
    old = client.post('/api/v1/buyer/auth/login',json={'phone':phone,'project_id':'project-1','password':data['password']})
    new = client.post('/api/v1/buyer/auth/login',json={'phone':phone,'project_id':'project-1','password':'replacement-good-pass-123'})
    assert old.status_code==401 and new.status_code==200
    listing=buyer_account_admin.main(['list','--project','project-1'])
    assert listing==0 and phone not in capsys.readouterr().out
    monkeypatch.setenv('APP_ENV','production')
    assert try_reset(('--verified-owner',))==1


def test_explicit_family_and_finance_do_not_generate_risky_model_drafts(client, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,'draft_contextual_reply',lambda *_: (_ for _ in ()).throw(AssertionError('No model draft for explicit family or finance')))
    a=client.post('/api/v1/leads',json={'name':'Buyer', 'phone':'9000000804', 'project_id':'project-1', 'source':'website', 'contact_consent':False})
    assert a.status_code == 201
    headers=bearer(a.json()['buyer_session_token'])
    for message, category, expected in [('My wife is not happy with the property','family','wife'),('My home loan is pending','financing','loan')]:
        response=client.post('/api/v1/buyer/conversations/messages',json={'message':message,'language':'en'},headers=headers)
        assert response.status_code==200, response.text
        body=response.json()
        assert body['reply_strategy']=='server_controlled'
        assert body['hesitation']['category']==category
        assert expected in body['reply'].lower()

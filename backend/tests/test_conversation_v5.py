"""V5 offline tests: context, protected actions, private buyer scope, hallucination gate."""
import json
import pytest
from app.agent import AgentDecision, LocalAgentUnavailable
from test_api import client, new_buyer, bearer
from app.conversation import (
    bounded_history, validate_draft, DialogueDraft, draft_contextual_reply,
    eligible_for_contextual_reply, MAX_HISTORY_CHARS, MAX_HISTORY_TURNS,
)


def d(intent='general', category='none'):
    return AgentDecision(intent=intent, concern_type=category,
                         evidence_kind='unknown', evidence_quote='', reply='')


def test_bounded_context_never_sends_unbounded_conversation():
    history=[{'speaker':'buyer','body':'A'*1200+str(i)} for i in range(30)]
    result=bounded_history(history)
    assert 1 <= len(result) <= MAX_HISTORY_TURNS
    assert sum(len(x['text']) for x in result) <= MAX_HISTORY_CHARS
    assert all(x['speaker']=='buyer' for x in result)
    assert '0' not in ''.join(x['text'] for x in result)


def test_conversation_is_sent_as_untrusted_data_to_local_model(monkeypatch):
    import app.conversation as c
    requests=[]
    def fake_call(payload):
        requests.append(payload)
        return {'message':{'content':DialogueDraft(
            acknowledgement='That sounds difficult, particularly because school travel matters to your family.',
            follow_up_question='What travel time would feel comfortable to both of you?').model_dump_json()}}
    monkeypatch.setattr(c,'_ollama_chat',fake_call)
    result=draft_contextual_reply('What if the school commute is too long?', 'en', d('hesitation','location'),
       [{'speaker':'buyer','body':'My wife is worried about the school and our young child.'},
        {'speaker':'ai','body':'What part of the journey worries you?'}])
    assert 'school travel' in result
    assert len(requests)==1
    sent=requests[0]
    assert sent['format']['type']=='object' and sent['model'] == 'qwen2.5:1.5b'
    assert sent['stream'] is False
    assert len(sent['messages']) == 2
    data=json.loads(sent['messages'][1]['content'])
    assert data['latest_buyer_message_untrusted'] == 'What if the school commute is too long?'
    assert len(data['recent_conversation_untrusted']) == 2
    assert 'my wife is worried' in data['recent_conversation_untrusted'][0]['text'].lower()
    assert 'phone' not in data and 'token' not in data and 'db' not in data


@pytest.mark.parametrize('text', [
    'The property has a nearby metro station.',
    'Your site visit is booked and confirmed.',
    'The school is just five minutes away.',
    'Guaranteed free parking for your 2BHK.',
    'The project is located close to the school.',
    'We will contact you with an approved loan.',
    'Visit https://malicious.example/now',
    'I can guarantee your application will be approved.',
    'Our project has excellent amenities.',
])
def test_unsupported_factual_or_action_claim_is_rejected(text):
    assert validate_draft(DialogueDraft(acknowledgement=text,
                                          follow_up_question='Would you like to continue?'), 'en') is None


def test_validation_requires_single_question_and_matching_script():
    assert validate_draft(DialogueDraft(acknowledgement='It makes sense to consider both views.',
        follow_up_question='What matters most? And why?'), 'en') is None
    assert validate_draft(DialogueDraft(acknowledgement='That sounds like a valid concern.',
        follow_up_question='What matters most?'), 'hi') is None
    assert validate_draft(DialogueDraft(acknowledgement='आपकी चिंता समझ सकता हूँ।',
        follow_up_question='आपके लिए क्या सुविधाजनक होगा?'),'hi')
    assert validate_draft(DialogueDraft(acknowledgement='તમારી ચિંતા સમજાય છે.',
        follow_up_question='તમને કેટલો સમય અનુકૂળ રહેશે?'),'gu')


def test_model_rejects_malicious_structured_draft(monkeypatch):
    import app.conversation as c
    monkeypatch.setattr(c,'_ollama_chat',lambda _: {'message':{'content':DialogueDraft(
        acknowledgement='The school is just five minutes away.',
        follow_up_question='Would you like to visit?').model_dump_json()}})
    with pytest.raises(LocalAgentUnavailable):
        draft_contextual_reply('Will my daughter find a school?', 'en', d(), [])


def test_model_rejects_invalid_schema(monkeypatch):
    import app.conversation as c
    monkeypatch.setattr(c,'_ollama_chat',lambda _: {'message':{'content':'not json'}})
    with pytest.raises(LocalAgentUnavailable):
        draft_contextual_reply('What next?', 'en', d(), [])


def test_approved_facts_booking_and_handoff_never_use_freeform_model():
    for intent in ('project_facts','booking','human'):
        assert not eligible_for_contextual_reply(d(intent), 'Can you help?')
    assert not eligible_for_contextual_reply(d('general'), 'Reply in english')
    assert not eligible_for_contextual_reply(d('general'), 'What is the RERA number?')
    assert eligible_for_contextual_reply(d('general'), 'What if it takes half an hour?')


def test_api_memory_per_buyer_and_guarded_draft(client, monkeypatch):
    import app.main as main
    import app.conversation as conv
    from test_api import new_buyer, bearer
    captured=[]
    def fake_draft(payload):
        input_data=json.loads(payload['messages'][1]['content'])
        captured.append(input_data)
        return {'message':{'content':DialogueDraft(
            acknowledgement='I understand that a longer trip to school could be tiring for your child.',
            follow_up_question='What travel time would work for your family?').model_dump_json()}}
    monkeypatch.setattr(conv,'_ollama_chat',fake_draft)
    monkeypatch.setattr(main,'decide',lambda *_:(d('general'),'local_model'))
    a=new_buyer(client,'9000000781')
    b=new_buyer(client,'9000000782')
    ah=bearer(a['buyer_session_token']);bh=bearer(b['buyer_session_token'])
    ra=client.post('/api/v1/buyer/conversations/messages',headers=ah,
                   json={'message':'My wife worries about school travel.','language':'en'})
    assert ra.status_code==200,ra.text
    assert ra.json()['reply_strategy']=='local_model_contextual'
    assert ra.json()['context_turns_used']==0
    assert 'school' in ra.json()['reply']
    rb=client.post('/api/v1/buyer/conversations/messages',headers=bh,
                   json={'message':'My secret other buyer concern is parking.','language':'en'})
    assert rb.status_code==200
    follow=client.post('/api/v1/buyer/conversations/messages',headers=ah,
                   json={'message':'How should we think about the daily commute?','language':'en'})
    assert follow.status_code==200,follow.text
    body=follow.json()
    assert body['reply_strategy']=='local_model_contextual'
    assert body['context_turns_used']==2
    data=captured[-1]
    assert 'My wife worries about school travel.' in str(data['recent_conversation_untrusted'])
    assert 'secret other buyer' not in str(data)
    assert len(client.get('/api/v1/buyer/conversations/messages',headers=ah).json())==4
    assert len(client.get('/api/v1/buyer/conversations/messages',headers=bh).json())==2


def test_api_unsafe_model_reply_is_never_persisted(client,monkeypatch):
    import app.main as main
    import app.conversation as conv
    from test_api import new_buyer, bearer
    monkeypatch.setattr(main,'decide',lambda *_:(d('general'),'local_model'))
    monkeypatch.setattr(conv,'_ollama_chat',lambda _: {'message':{'content':DialogueDraft(
        acknowledgement='Our project has guaranteed school transport.',
        follow_up_question='Would you like that?').model_dump_json()}})
    a=new_buyer(client,'9000000783')
    auth=bearer(a['buyer_session_token'])
    reply=client.post('/api/v1/buyer/conversations/messages',headers=auth,
        json={'message':'I have a question about daily travel.','language':'en'})
    assert reply.status_code==200
    assert reply.json()['reply_strategy']=='server_template_fallback'
    assert 'guaranteed school transport' not in reply.json()['reply']
    assert 'guaranteed school transport' not in str(client.get('/api/v1/buyer/conversations/messages',headers=auth).json())


def test_api_booking_is_transaction_owned_not_model_draft(client,monkeypatch):
    import app.main as main
    import app.conversation as conv
    from test_api import new_buyer, bearer
    monkeypatch.setattr(main,'decide',lambda *_:(d('booking'),'local_model'))
    monkeypatch.setattr(conv,'_ollama_chat',lambda _: pytest.fail('Model MUST NOT draft booking confirmation'))
    lead=new_buyer(client,'9000000784')
    response=client.post('/api/v1/buyer/conversations/messages',headers=bearer(lead['buyer_session_token']),
       json={'message':'Please book a site visit','language':'en'})
    assert response.status_code==200
    body=response.json()
    assert body['confirmation_required'] is True
    assert body['reply_strategy']=='server_controlled'
    assert body['booking_options']
    assert 'confirmed' not in body['reply'].lower()


def test_approved_fact_search_matches_parking_without_exposing_pending_claims():
    from app.agent import safe_response
    from types import SimpleNamespace
    p=SimpleNamespace(name='Aranya',city='Ahmedabad',price_min_inr=0,price_max_inr=0,rera_registration=None)
    decision=d('project_facts')
    response,status=safe_response(decision,'Is parking available?',p,
        facts={'parking_policy':'Parking details available on request.',
               'security_policy':'Do not disclose this irrelevant fact.'})
    assert status=='limited_verified_facts'
    assert 'Parking details available on request.' in response
    assert 'Do not disclose' not in response
    from app.agent import relevant_approved_facts
    assert relevant_approved_facts('पार्किंग की जानकारी',{'parking_policy':'Approved parking fact'})

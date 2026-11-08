"""V5.1: current message wins over unrelated older conversation context."""
from types import SimpleNamespace
import pytest
from app.agent import AgentDecision, is_verified_fact_query, is_pending_finance_concern, route_latest_message, safe_response
from app.conversation import eligible_for_contextual_reply, DialogueDraft
from test_api import client, new_buyer, bearer


def decision(intent='general', category='none', evidence=''):
    return AgentDecision(intent=intent,concern_type=category,
                         evidence_kind='explicit' if evidence else 'unknown',
                         evidence_quote=evidence,reply='')


def test_current_message_routing_facts_and_finance():
    assert is_verified_fact_query('What project details are verified?')
    assert is_verified_fact_query('Show me approved facts')
    assert is_pending_finance_concern('My home loan is pending.')
    assert not is_pending_finance_concern('What are the loan requirements?')
    assert not is_verified_fact_query('My wife is not happy with this property')
    old_family=decision('hesitation','family','some previous text')
    facts=route_latest_message(old_family,'What project details are verified?')
    assert facts.intent=='project_facts' and facts.concern_type=='none' and not facts.evidence_quote
    assert not eligible_for_contextual_reply(decision(), 'What project details are verified?')
    loan=route_latest_message(decision('project_facts'), 'My home loan is pending.')
    assert loan.intent=='hesitation' and loan.concern_type=='financing'
    assert loan.evidence_kind=='explicit' and loan.evidence_quote=='My home loan is pending.'


def test_verified_fact_answer_uses_revisions_not_demo_prices():
    project=SimpleNamespace(name='Demo',city='Ahmedabad',price_min_inr=6500000,
                            price_max_inr=12000000,rera_registration='DEMO-UNREVIEWED')
    d=decision('project_facts')
    text,_=safe_response(d,'What project details are verified?',project,facts={})
    assert 'detailed project fact sheet has not been published' in text.lower()
    assert '65,00,000' not in text and '12000000' not in text
    assert 'DEMO-UNREVIEWED' not in text
    approved,_=safe_response(decision('project_facts'), 'What project details are verified?', project,
        facts={'parking_policy':'Parking allocations to be confirmed by sales head.',
               'possession_status':'Possession status available upon request.'})
    assert 'Parking allocations to be confirmed' in approved
    assert 'Possession status available upon request' in approved
    assert 'DEMO-UNREVIEWED' not in approved


def test_api_facts_question_does_not_reuse_previous_wife_context(client,monkeypatch):
    import app.main as main
    import app.conversation as conv
    a=new_buyer(client,'9000000891'); auth=bearer(a['buyer_session_token'])
    monkeypatch.setattr(main,'decide',lambda *_:(decision('general'),'local_model'))
    monkeypatch.setattr(conv,'_ollama_chat',lambda _: {'message':{'content':DialogueDraft(
        acknowledgement='I understand that both of you want to feel comfortable with the choice.',
        follow_up_question='What concerns your wife most?').model_dump_json()}})
    history=client.post('/api/v1/buyer/conversations/messages',headers=auth,
        json={'message':'My wife is not happy with the property.','language':'en'})
    assert history.status_code==200,history.text
    # Model drafts are not eligible for approved-fact questions even when it labels them general.
    monkeypatch.setattr(conv,'_ollama_chat',lambda _:pytest.fail('Fact query must never be a freeform model draft'))
    first=client.post('/api/v1/buyer/conversations/messages',headers=auth,
                      json={'message':'What project details are verified?','language':'en'})
    assert first.status_code==200,first.text
    response=first.json()
    assert response['reply_strategy']=='server_controlled'
    assert response['grounding_status']=='limited_verified_facts'
    assert 'detailed project fact sheet has not been published' in response['reply'].lower()
    assert response['context_turns_used']==0
    assert 'wife' not in response['reply'].lower()
    assert response['build']=='sitepilot-reliability-v7.2'


def test_api_pending_loan_after_family_history_rejects_off_topic_reply(client,monkeypatch):
    import app.main as main
    import app.conversation as conv
    a=new_buyer(client,'9000000892'); auth=bearer(a['buyer_session_token'])
    monkeypatch.setattr(main,'decide',lambda *_:(decision('general'),'local_model'))
    monkeypatch.setattr(conv,'_ollama_chat',lambda _: {'message':{'content':DialogueDraft(
        acknowledgement='I understand your wife and family have concerns about the home.',
        follow_up_question='Would you like to discuss those family concerns?').model_dump_json()}})
    # A family topic appears before the buyer raises a NEW financial concern.
    first=client.post('/api/v1/buyer/conversations/messages',headers=auth,
        json={'message':'My wife is not happy with the property.','language':'en'})
    assert first.status_code==200
    newer=client.post('/api/v1/buyer/conversations/messages',headers=auth,
        json={'message':'My home loan is pending.','language':'en'})
    assert newer.status_code==200,newer.text
    body=newer.json()
    assert body['hesitation']['category']=='financing'
    assert body['reply_strategy']=='server_controlled'
    assert 'loan' in body['reply'].lower()
    assert 'wife' not in body['reply'].lower()
    assert 'loan is pending' in body['hesitation']['evidence'].lower()
    assert body['build']=='sitepilot-reliability-v7.2'

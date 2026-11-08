from types import SimpleNamespace
from app.agent import AgentDecision,safe_response, classify_with_sitepilot, LocalAgentUnavailable
import pytest

def decision(**kwargs):
    return AgentDecision(intent='hesitation',concern_type='financing',evidence_kind='explicit',
                         evidence_quote='loan is pending',reply='You are approved for a loan!',**kwargs)

def test_unsafe_claim_blocked():
    p=SimpleNamespace(name='Demo',city='Ahmedabad',price_min_inr=6500000,price_max_inr=12000000,rera_registration=None)
    response,source=safe_response(decision(),'My loan is pending.',p)
    assert 'approved for a loan' not in response
    assert source=='concern_acknowledged'

def test_forged_evidence_discarded():
    p=SimpleNamespace(name='Demo',city='Ahmedabad',price_min_inr=6500000,price_max_inr=12000000,rera_registration=None)
    d=decision()
    response,_=safe_response(d,'I am just browsing.',p)
    assert d.concern_type=='none' and d.evidence_kind=='unknown'

def test_project_claims_from_verified_fields_only():
    p=SimpleNamespace(name='Demo',city='Ahmedabad',price_min_inr=6500000,price_max_inr=12000000,rera_registration=None)
    d=AgentDecision(intent='project_facts',concern_type='none',evidence_kind='unknown',reply='Pool and possession guaranteed')
    response,source=safe_response(d,'Does it have a pool?',p)
    assert source=='limited_verified_facts'
    assert 'Pool and possession guaranteed' not in response
    assert 'not have verified' in response

def test_without_key_does_not_fake_ai(monkeypatch):
    monkeypatch.setenv('SITEPILOT_MODEL_URL','https://remote.example')
    with pytest.raises(LocalAgentUnavailable): classify_with_sitepilot('Hello','en','Demo')

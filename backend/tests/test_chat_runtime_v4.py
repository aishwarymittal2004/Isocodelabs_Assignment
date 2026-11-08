from types import SimpleNamespace
import pytest
from app.agent import AgentDecision, preferred_language, is_language_switch, decide, ground_obvious_concern, safe_response

PROJECT = SimpleNamespace(name='Aranya', city='Ahmedabad',price_min_inr=0,price_max_inr=0,rera_registration=None)

@pytest.mark.parametrize('message,selected,expected', [
    ('Reply in english','hi','en'),
    ('Please continue in English','gu','en'),
    ('Speak Gujarati please','en','gu'),
    ('Kya aap hindi me baat kr skte h?','en','hi'),
    ('I am interested in your project','hi','hi'),
])
def test_requested_language_overrides_selector(message,selected,expected):
    assert preferred_language(message,selected)==expected


def test_english_switch_is_model_independent(monkeypatch):
    monkeypatch.setenv('SITEPILOT_MODEL_URL','https://untrusted.example')
    msg='Reply in english'
    assert is_language_switch(msg)
    language=preferred_language(msg,'hi')
    decision,mode=decide(msg,language,'Aranya')
    response,status=safe_response(decision,msg,PROJECT,language=language)
    assert mode=='local_policy' and status=='language_preference_acknowledged'
    assert 'continue in English' in response


def test_school_accessibility_outweighs_general_classification():
    msg='My wife is worried because the school is too far away, and our child is only five years old.'
    decision=AgentDecision(intent='general',concern_type='none',evidence_kind='unknown',reply='')
    grounded=ground_obvious_concern(decision,msg)
    assert grounded.concern_type=='location' and grounded.evidence_kind=='explicit'
    response,status=safe_response(grounded,msg,PROJECT,language='en')
    assert status=='concern_acknowledged'
    assert 'five-year-old' in response and 'verified school distances' in response
    assert 'nearest school is' not in response


def test_school_response_honors_hindi_and_does_not_invent_distance():
    msg='The school is too far away.'
    grounded=ground_obvious_concern(AgentDecision(intent='general', concern_type='none', evidence_kind='unknown',reply=''),msg)
    response,_=safe_response(grounded,msg,PROJECT,language='hi')
    assert 'स्कूल' in response and 'सत्यापित' in response

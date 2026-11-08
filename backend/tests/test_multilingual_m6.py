"""Offline checks: local model prose cannot override approved templates, including translations."""
from types import SimpleNamespace
import pytest
from app.agent import AgentDecision, safe_response, translated_reply

PROJECT = SimpleNamespace(name='Demo Project', city='Ahmedabad',
    price_min_inr=6500000, price_max_inr=12000000, rera_registration=None)

def make_decision(intent, concern='none', evidence='', kind='unknown'):
    return AgentDecision(intent=intent, concern_type=concern, evidence_kind=kind,
        evidence_quote=evidence, reply='Guaranteed loan approval and discount', needs_human=False)

@pytest.mark.parametrize('lang,token', [('en','available'), ('hi','उपलब्ध'), ('gu','ઉપલબ્ધ')])
def test_translated_booking_remains_non_committal(lang,token):
    reply, status = safe_response(make_decision('booking'), 'Book a visit', PROJECT, language=lang)
    assert status == 'booking_tool_required' and token in reply
    assert 'Guaranteed loan approval' not in reply

@pytest.mark.parametrize('lang,token', [('en','concern'), ('hi','चिंता'), ('gu','ચિંતા')])
def test_hesitation_preserves_verified_evidence(lang,token):
    d = make_decision('hesitation','financing','loan pending','explicit')
    reply, status = safe_response(d,'My loan pending',PROJECT,language=lang)
    assert token in reply and status == 'concern_acknowledged'

@pytest.mark.parametrize('lang', ['en','hi','gu'])
def test_forged_evidence_dropped_for_all_languages(lang):
    d = make_decision('hesitation','financing','loan pending','explicit')
    response, _ = safe_response(d, 'Just exploring', PROJECT, language=lang)
    assert d.concern_type == 'none' and d.evidence_kind == 'unknown'
    assert response == translated_reply(lang,'general')

@pytest.mark.parametrize('lang', ['en','hi','gu'])
def test_unapproved_model_facts_never_repeated(lang):
    reply, status = safe_response(make_decision('project_facts'), 'Pool?', PROJECT, facts={}, language=lang)
    assert status == 'limited_verified_facts'
    assert 'Guaranteed loan approval' not in reply
    assert 'pool' not in reply.casefold()

@pytest.mark.parametrize('lang', ['en','hi','gu'])
def test_no_slots_fallback_has_translation(lang):
    assert translated_reply(lang,'no_slots') != translated_reply(lang,'slots')

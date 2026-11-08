"""Regressions for real buyer complaints observed in the SitePilot browser."""
from types import SimpleNamespace
from app.agent import AgentDecision, preferred_language, ground_obvious_concern, safe_response

PROJECT = SimpleNamespace(name='Aranya Residences', city='Ahmedabad', price_min_inr=6500000,
                          price_max_inr=12000000, rera_registration=None)


def model_general():
    return AgentDecision(intent='general', concern_type='none', evidence_kind='unknown',
                         evidence_quote='', reply='Generic or unsupported model prose')


def test_family_concern_from_actual_screenshot_overrides_generic_classifier():
    message = 'I found this property very good and I am interested in this but my wife is not happy with this property'
    d = ground_obvious_concern(model_general(), message)
    reply, status = safe_response(d, message, PROJECT)
    assert d.intent == 'hesitation'
    assert d.concern_type == 'family'
    assert d.evidence_quote in message
    assert status == 'concern_acknowledged'
    assert 'wife' in reply and 'without pressure' in reply
    assert 'Generic or unsupported model prose' not in reply


def test_romanized_hindi_request_from_actual_screenshot():
    message = 'Kya aap hindi me baat kr skte h?'
    language = preferred_language(message, 'en')
    assert language == 'hi'
    reply, status = safe_response(model_general(), message, PROJECT, language=language)
    assert status == 'language_preference_acknowledged'
    assert 'हिंदी' in reply


def test_gujarati_and_hindi_native_script_auto_detected():
    assert preferred_language('શું તમે મદદ કરશો?', 'en') == 'gu'
    assert preferred_language('मुझे यह घर पसंद है', 'en') == 'hi'


def test_explicit_ui_preference_wins_when_message_has_no_switch():
    assert preferred_language('Can you help me?', 'gu') == 'gu'
    assert preferred_language('I want a 2BHK', 'en') == 'en'


def test_forged_property_claim_still_blocked():
    d = model_general()
    d.reply = 'Guaranteed free parking and immediate possession'
    reply, _ = safe_response(d, 'Hello!', PROJECT)
    assert 'Guaranteed free parking' not in reply


def test_neutral_family_mention_is_not_automatically_hesitation():
    d = ground_obvious_concern(model_general(), 'My wife and I will visit on Sunday.')
    assert d.concern_type == 'none'

"""New local agent and offline-trained fallback tests. All synthetic examples."""
import io
import json
from unittest.mock import patch
import pytest
from app.agent import (
    classify_with_sitepilot, classify_with_trained_intent, decide,
    LocalAgentUnavailable, AgentDecision, safe_response
)
from app.local_intent import classify_intent, MODEL_PATH


def test_classifier_is_trained_and_can_detect_booking():
    assert MODEL_PATH.exists(), 'Commit the synthetic-data trained model artifact'
    assert classify_intent('I want to book a site visit')[0] == 'booking'


def test_classifier_supports_hindi_gujarati():
    assert classify_intent('मुझे रविवार को फ्लैट देखने आना है')[0] == 'booking'
    assert classify_intent('મારે સાઇટ વિઝિટ બુક કરવી છે')[0] == 'booking'


def test_fallback_offline_requires_no_api_key(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setenv('SITEPILOT_MODEL_URL', 'http://127.0.0.1:1')
    monkeypatch.setenv('SITEPILOT_MODEL_TIMEOUT', '0.1')
    monkeypatch.setenv('SITEPILOT_ALLOW_CLASSIFIER_FALLBACK', 'true')
    decision, mode = decide('I want to book a site visit', 'en', 'Demo')
    assert mode == 'local_classifier'
    assert decision.intent == 'booking'


def test_remote_ollama_endpoint_refused(monkeypatch):
    monkeypatch.setenv('SITEPILOT_MODEL_URL', 'https://api.provider.example')
    with pytest.raises(LocalAgentUnavailable):
        classify_with_sitepilot('Can I book a visit?', 'en', 'Demo')


def test_local_model_structured_output(monkeypatch):
    import app.agent as a
    monkeypatch.setenv('SITEPILOT_MODEL_URL', 'http://127.0.0.1:11434')
    result = AgentDecision(intent='booking', concern_type='none', evidence_kind='unknown',
                           evidence_quote='', reply='Your apartment is reserved!')
    wrapped = {'message': {'content': result.model_dump_json()}}

    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, *args): return json.dumps(wrapped).encode()

    captured = []
    def fake_open(request, timeout):
        captured.append(json.loads(request.data))
        return FakeResponse()
    class FakeOpener:
        def open(self, request, timeout):
            return fake_open(request, timeout)
    monkeypatch.setattr('urllib.request.build_opener', lambda *handlers: FakeOpener())
    decision = classify_with_sitepilot('Book me a visit', 'en', 'Demo')
    assert decision.intent == 'booking'
    assert captured[0]['stream'] is False
    assert captured[0]['model'] == 'qwen2.5:1.5b'
    assert 'GEMINI_API_KEY' not in json.dumps(captured)
    from types import SimpleNamespace
    p = SimpleNamespace(name='Demo', city='Ahmedabad', price_min_inr=6500000,
                        price_max_inr=12000000, rera_registration=None)
    safe, state = safe_response(decision, 'Book me a visit', p)
    assert 'reserved!' not in safe
    assert state == 'booking_tool_required'


def test_classifier_does_not_invent_evidence():
    d = classify_with_trained_intent('Just browsing', 'en', 'Demo')
    assert d.evidence_quote == ''
    assert d.concern_type == 'none'

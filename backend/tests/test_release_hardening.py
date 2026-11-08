"""Self-contained deployment and configuration regression tests."""
from types import SimpleNamespace
import pytest
from app.agent import _ollama_url, LocalAgentUnavailable, decide


def test_local_ollama_is_permitted_by_default(monkeypatch):
    monkeypatch.setenv('SITEPILOT_MODEL_URL', 'http://127.0.0.1:11434')
    monkeypatch.delenv('SITEPILOT_MODEL_ALLOWED_HOSTS', raising=False)
    assert _ollama_url() == 'http://127.0.0.1:11434'


def test_approved_private_host_with_https(monkeypatch):
    monkeypatch.setenv('SITEPILOT_MODEL_ALLOWED_HOSTS', 'ollama.internal')
    monkeypatch.setenv('SITEPILOT_MODEL_URL', 'https://ollama.internal:11434')
    assert _ollama_url() == 'https://ollama.internal:11434'


def test_private_http_requires_opt_in(monkeypatch):
    monkeypatch.setenv('SITEPILOT_MODEL_ALLOWED_HOSTS', 'ollama.railway.internal')
    monkeypatch.setenv('SITEPILOT_MODEL_URL', 'http://ollama.railway.internal:11434')
    monkeypatch.delenv('SITEPILOT_ALLOW_PRIVATE_HTTP', raising=False)
    with pytest.raises(LocalAgentUnavailable):
        _ollama_url()
    monkeypatch.setenv('SITEPILOT_ALLOW_PRIVATE_HTTP', 'true')
    assert _ollama_url() == 'http://ollama.railway.internal:11434'


@pytest.mark.parametrize('url', [
    'https://unknown.example:11434',
    'http://ollama.internal:11434/redirect',
    'http://user:pass@ollama.internal:11434',
    'http://ollama.internal:abc',
    'http://ollama.internal:11434?token=x',
    'file:///etc/passwd',
])
def test_invalid_model_endpoints_fail_closed(monkeypatch, url):
    monkeypatch.setenv('SITEPILOT_MODEL_ALLOWED_HOSTS', 'ollama.internal')
    monkeypatch.setenv('SITEPILOT_MODEL_URL', url)
    monkeypatch.setenv('SITEPILOT_ALLOW_PRIVATE_HTTP', 'true')
    with pytest.raises(LocalAgentUnavailable):
        _ollama_url()


def test_production_disables_classifier_fallback_by_default(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('SITEPILOT_ALLOW_CLASSIFIER_FALLBACK', raising=False)
    monkeypatch.setenv('SITEPILOT_MODEL_URL', 'https://untrusted.example:11434')
    with pytest.raises(LocalAgentUnavailable):
        decide('Can I book a visit?', 'en', 'Example')


def test_readiness_works_and_database_errors_are_masked():
    from app.main import ready
    from fastapi import HTTPException
    class GoodDB:
        def execute(self, stmt): return 1
    class BadDB:
        def execute(self, stmt): raise RuntimeError('secret-connection-string')
    assert ready(GoodDB())['status'] == 'ready'
    with pytest.raises(HTTPException) as exc:
        ready(BadDB())
    assert exc.value.status_code == 503
    assert 'secret-' not in str(exc.value.detail)

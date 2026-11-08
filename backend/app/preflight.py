"""Safe, read-only preflight checks for SitePilot local demo and cloud deployment.

Run: python -m app.preflight
Does NOT print passwords, tokens, URLs with credentials, or customer data.
Does NOT create or modify the database.
"""
import json
import os
import sys
from urllib.request import Request, build_opener, ProxyHandler
from .core import engine
from .agent import _ollama_url, LocalAgentUnavailable
from sqlalchemy import text


def run_preflight() -> int:
    ok = True
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        print('[OK] Database connection')
    except Exception:
        print('[FAIL] Database connection (check DATABASE_URL and PostgreSQL availability)')
        ok = False

    try:
        endpoint = _ollama_url()
        model = os.getenv('SITEPILOT_MODEL', 'qwen2.5:1.5b')
        # /api/tags returns model metadata only; never send user data.
        opener = build_opener(ProxyHandler({}))
        with opener.open(Request(endpoint + '/api/tags'), timeout=4) as response:
            models = json.load(response).get('models', [])
        names = {item.get('name') for item in models}
        if model in names or any(n and n.split(':')[0] == model and ':' not in model for n in names):
            print('[OK] Local/private model server reachable; selected model installed')
        else:
            print('[FAIL] Model server reachable, but requested SITEPILOT_MODEL is not installed')
            ok = False
    except (LocalAgentUnavailable, Exception):
        print('[FAIL] Model server unavailable or misconfigured (check Ollama and SITEPILOT_MODEL_URL)')
        ok = False

    if os.getenv('APP_ENV', 'development').lower() == 'production':
        configured = os.getenv('SITEPILOT_ALLOW_CLASSIFIER_FALLBACK', 'false').lower() == 'true'
        print('[WARN] Classifier fallback enabled in production' if configured else '[OK] Production fallback disabled')

    print('Preflight:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(run_preflight())

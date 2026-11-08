import importlib
import os
import subprocess
import sys


def test_production_rejects_insecure_defaults():
    code = 'import app.core'
    env = os.environ.copy()
    env.update({'APP_ENV': 'production', 'DATABASE_URL': 'sqlite:///./should-not-create.db', 'JWT_SECRET': 'short'})
    child = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    assert child.returncode != 0
    assert 'PostgreSQL DATABASE_URL is required' in child.stderr


def test_cors_preflight_allows_local_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path}/cors.db')
    monkeypatch.setenv('JWT_SECRET','test-only-secret-longer-than-thirty-two-chars')
    import app.core, app.models, app.main
    importlib.reload(app.core);importlib.reload(app.models);importlib.reload(app.main)
    client=TestClient(app.main.app)
    response=client.options('/api/v1/leads', headers={
        'Origin':'http://localhost:3000',
        'Access-Control-Request-Method':'POST',
        'Access-Control-Request-Headers':'content-type'})
    assert response.status_code == 200
    assert response.headers.get('access-control-allow-origin') == 'http://localhost:3000'

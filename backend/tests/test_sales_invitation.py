
"""Staff invitations and buyer account recovery: no Ollama or PostgreSQL needed."""

import importlib
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        'DATABASE_URL',
        f'sqlite:///{tmp_path}/invitations.db'
    )
    monkeypatch.setenv(
        'JWT_SECRET',
        'test-only-secret-with-at-least-32-characters'
    )
    monkeypatch.setenv(
        'DEMO_SALES_EMAIL',
        'reviewer@example.test'
    )
    monkeypatch.setenv(
        'DEMO_SALES_PASSWORD',
        'test-password'
    )
    monkeypatch.setenv(
        'SALES_HEAD_EMAIL',
        'reviewer@example.test'
    )
    monkeypatch.setenv(
        'SITEPILOT_MODEL_URL',
        'https://untrusted.example'
    )

    # Import all application and ticket modules.
    import app.core
    import app.models
    import app.tickets_models
    import app.ticket_flow
    import app.tickets_router
    import app.main
    import app.seed

    # Reload the SQLAlchemy Base and models in dependency order.
    # This registers buyer_tickets and related tables before seed().
    importlib.reload(app.core)
    importlib.reload(app.models)
    importlib.reload(app.tickets_models)
    importlib.reload(app.ticket_flow)
    importlib.reload(app.tickets_router)
    importlib.reload(app.main)
    importlib.reload(app.seed)

    # Create and seed the isolated SQLite test database.
    app.seed.seed()

    with TestClient(app.main.app) as c:
        yield c


def head_token(c):
    response = c.post(
        '/api/v1/auth/login',
        json={
            'email': 'reviewer@example.test',
            'password': 'test-password'
        }
    )
    assert response.status_code == 200, response.text
    return response.json()['access_token']


def bearer(t):
    return {'Authorization': f'Bearer {t}'}


def test_invite_sales_executive_and_activate_login_and_team_list(client):
    head = head_token(client)

    assert client.get('/api/v1/sales/team').status_code == 401

    invited = client.post(
        '/api/v1/sales/invitations',
        headers=bearer(head),
        json={
            'email': 'New.Example@EXAMPLE.TEST',
            'display_name': 'New Executive'
        }
    )

    assert invited.status_code == 201, invited.text

    invitation = invited.json()

    assert invitation['email'] == 'new.example@example.test'
    assert len(invitation['invitation_code']) >= 40

    import app.core as core
    from app.models import SalesInvitation

    with core.SessionLocal() as db:
        record = db.scalar(
            select(SalesInvitation).where(
                SalesInvitation.email == invitation['email']
            )
        )

        assert record
        assert record.token_hash != invitation['invitation_code']
        assert len(record.token_hash) == 64

    activated = client.post(
        '/api/v1/auth/accept-invitation',
        json={
            'email': 'new.example@example.test',
            'invitation_code': invitation['invitation_code'],
            'password': 'new-user-password-is-long'
        }
    )

    assert activated.status_code == 201, activated.text
    assert 'access_token' not in activated.json()

    assert client.post(
        '/api/v1/auth/accept-invitation',
        json={
            'email': 'new.example@example.test',
            'invitation_code': invitation['invitation_code'],
            'password': 'another-user-password'
        }
    ).status_code == 400

    login = client.post(
        '/api/v1/auth/login',
        json={
            'email': 'new.example@example.test',
            'password': 'new-user-password-is-long'
        }
    )

    assert login.status_code == 200

    staff = login.json()['access_token']

    assert client.get(
        '/api/v1/auth/me',
        headers=bearer(staff)
    ).json()['role'] == 'sales'

    assert client.get(
        '/api/v1/sales/team',
        headers=bearer(staff)
    ).status_code == 403

    assert client.post(
        '/api/v1/sales/invitations',
        headers=bearer(staff),
        json={
            'email': 'other@example.test',
            'display_name': 'Another'
        }
    ).status_code == 403

    users = client.get(
        '/api/v1/sales/team',
        headers=bearer(head)
    ).json()

    assert any(
        x['email'] == 'new.example@example.test'
        and x['role'] == 'sales'
        for x in users
    )

    assert not any(
        'password_hash' in x
        for x in users
    )


def test_invalid_expired_and_replaced_codes(client):
    head = head_token(client)

    path = '/api/v1/sales/invitations'
    data = {
        'email': 'newuser@example.test',
        'display_name': 'New User'
    }

    first = client.post(
        path,
        headers=bearer(head),
        json=data
    ).json()['invitation_code']

    second = client.post(
        path,
        headers=bearer(head),
        json=data
    ).json()['invitation_code']

    assert first != second

    for code, email in [
        (first, data['email']),
        (second, 'wrong@example.test'),
        ('x' * 45, data['email'])
    ]:
        assert client.post(
            '/api/v1/auth/accept-invitation',
            json={
                'email': email,
                'invitation_code': code,
                'password': 'long-test-password'
            }
        ).status_code == 400

    # A valid token is valid only until its expiry time.
    import app.core as core
    from app.models import SalesInvitation
    import hashlib

    with core.SessionLocal() as db:
        record = db.scalar(
            select(SalesInvitation).where(
                SalesInvitation.token_hash ==
                hashlib.sha256(second.encode()).hexdigest()
            )
        )

        record.expires_at = core.now() - timedelta(seconds=1)
        db.commit()

    assert client.post(
        '/api/v1/auth/accept-invitation',
        json={
            'email': data['email'],
            'invitation_code': second,
            'password': 'long-test-password'
        }
    ).status_code == 400


def test_no_sales_invitation_from_buyer_or_anonymous(client):
    buyer = client.post(
        '/api/v1/leads',
        json={
            'name': 'Buyer',
            'phone': '9000000199',
            'project_id': 'project-1',
            'source': 'website',
            'contact_consent': False
        }
    ).json()['buyer_session_token']

    path = '/api/v1/sales/invitations'

    payload = {
        'email': 'staff@example.test',
        'display_name': 'Staff'
    }

    assert client.post(
        path,
        json=payload
    ).status_code == 401

    assert client.post(
        path,
        json=payload,
        headers=bearer(buyer)
    ).status_code == 403

    assert client.post(
        '/api/v1/auth/accept-invitation',
        json={
            'email': payload['email'],
            'invitation_code': 'x' * 40,
            'password': 'long-test-password'
        }
    ).status_code == 400


def test_existing_buyer_legacy_jwt_is_not_a_password_account(client):
    payload = {
        'name': 'Existing Lead',
        'phone': '9000000299',
        'project_id': 'project-1',
        'source': 'website',
        'contact_consent': False
    }

    lead = client.post(
        '/api/v1/leads',
        json=payload
    ).json()

    login = {
        'phone': '9000000299',
        'password': 'long-password-here',
        'project_id': 'project-1'
    }

    assert client.post(
        '/api/v1/buyer/auth/login',
        json=login
    ).status_code == 401

    assert client.post(
        '/api/v1/buyer/auth/claim',
        headers=bearer(lead['buyer_session_token']),
        json={'password': 'long-password-here'}
    ).status_code == 201

    signed = client.post(
        '/api/v1/buyer/auth/login',
        json=login
    )

    assert signed.status_code == 200
    assert signed.json()['lead_id'] == lead['lead_id']

    # Credential remains scoped to the original project.
    assert client.post(
        '/api/v1/buyer/auth/login',
        json={
            **login,
            'project_id': 'project-2'
        }
    ).status_code == 401

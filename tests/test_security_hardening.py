from datetime import UTC, datetime, timedelta

import pytest

from database.db import db
from models.finance import Finance
from models.user import User
from services.calculations import get_monthly_stats, get_yearly_stats


def test_health_endpoint_reports_ok(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.json == {'status': 'ok', 'database': 'ok'}


def test_security_headers_are_present(client):
    response = client.get('/')

    assert response.status_code == 200
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'DENY'
    csp = response.headers['Content-Security-Policy']
    assert "default-src 'self'" in csp
    assert "script-src 'self' 'nonce-" in csp
    assert "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com" in csp
    assert "'unsafe-inline'" not in csp.split('script-src', 1)[1].split(';', 1)[0]
    assert "'unsafe-inline'" not in csp.split('style-src', 1)[1].split(';', 1)[0]
    assert b'<script nonce="' in response.data


def test_goal_and_budget_pages_render_without_inline_style_attributes(client, app):
    with app.app_context():
        user = User(username='stylecheck', email='stylecheck@example.com')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    client.post(
        '/login',
        data={'identifier': 'stylecheck', 'password': 'Password123'},
        follow_redirects=True,
    )

    goals_response = client.get('/goals')
    budgets_response = client.get('/budgets')

    assert goals_response.status_code == 200
    assert budgets_response.status_code == 200
    assert b'style=' not in goals_response.data
    assert b'style=' not in budgets_response.data


def test_yearly_stats_are_scoped_by_user(app):
    with app.app_context():
        first_user = User(username='alice', email='alice@example.com')
        first_user.set_password('Password123')
        second_user = User(username='bob', email='bob@example.com')
        second_user.set_password('Password123')
        db.session.add_all([first_user, second_user])
        db.session.commit()

        db.session.add_all([
            Finance(
                description='Salary',
                value=5000,
                category='Salary',
                type='Receita',
                status='Pago',
                due_date=datetime(2026, 3, 5).date(),
                user_id=first_user.id,
            ),
            Finance(
                description='Rent',
                value=1000,
                category='Housing',
                type='Despesa',
                status='Pago',
                due_date=datetime(2026, 3, 10).date(),
                user_id=second_user.id,
            ),
        ])
        db.session.commit()

        stats = get_yearly_stats(2026, user_id=first_user.id)

        assert stats['total_receitas'] == 5000
        assert stats['total_despesas'] == 0
        assert stats['saldo'] == 5000
        assert stats['by_month'][3]['receitas'] == 5000


def test_monthly_stats_requires_user_scope():
    with pytest.raises(ValueError, match='user_id is required'):
        get_monthly_stats(3, 2026, user_id=None)


def test_forgot_password_uses_generic_response_for_missing_user(client):
    response = client.post(
        '/forgot_password',
        data={'identifier': 'missing-user', 'method': 'offline'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Se existir uma conta correspondente' in response.data
    assert b'Chave de Recupera' in response.data


def test_offline_reset_password_works_without_user_id_in_url(client, app):
    with app.app_context():
        user = User(username='recoverme', email='recover@example.com')
        user.set_password('Password123')
        user.set_recovery_key('ABCD1234EFGH5678')
        db.session.add(user)
        db.session.commit()

    response = client.post(
        '/reset_password/offline',
        data={
            'identifier': 'recoverme',
            'recovery_key': 'ABCD1234EFGH5678',
            'new_password': 'NewPassword123',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Sua senha foi atualizada com sucesso' in response.data

    login_response = client.post(
        '/login',
        data={'identifier': 'recoverme', 'password': 'NewPassword123'},
        follow_redirects=True,
    )
    assert b'Novo Lan' in login_response.data


def test_login_lockout_blocks_access_after_repeated_failures(client, app):
    with app.app_context():
        user = User(username='lockeduser', email='locked@example.com')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    for _ in range(5):
        response = client.post(
            '/login',
            data={'identifier': 'lockeduser', 'password': 'wrongpassword'},
            follow_redirects=True,
        )

    assert b'Muitas tentativas de acesso foram detectadas' in response.data

    blocked_response = client.post(
        '/login',
        data={'identifier': 'lockeduser', 'password': 'Password123'},
        follow_redirects=True,
    )
    assert b'Muitas tentativas de acesso foram detectadas' in blocked_response.data

    with app.app_context():
        locked_user = User.query.filter_by(username='lockeduser').first()
        locked_user.locked_until = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
        db.session.commit()

    recovered_response = client.post(
        '/login',
        data={'identifier': 'lockeduser', 'password': 'Password123'},
        follow_redirects=True,
    )
    assert b'Novo Lan' in recovered_response.data


def test_check_username_and_email_validation_endpoints(client, app):
    with app.app_context():
        user = User(username='lookupuser', email='lookup@example.com')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    username_response = client.post('/check_username', json={'username': 'lookupuser'})
    assert username_response.status_code == 200
    username_payload = username_response.get_json()
    assert username_payload['available'] is True
    assert username_payload['verified'] is False
    assert 'cadastro' in username_payload['message']

    invalid_username_response = client.post('/check_username', json={'username': ''})
    assert invalid_username_response.status_code == 400

    email_response = client.post('/check_email', json={'email': 'lookup@example.com'})
    assert email_response.status_code == 200
    email_payload = email_response.get_json()
    assert email_payload['available'] is True
    assert email_payload['verified'] is False
    assert 'cadastro' in email_payload['message']

    invalid_email_response = client.post('/check_email', json={'email': 'invalid'})
    assert invalid_email_response.status_code == 400


def test_forgot_password_rejects_invalid_method(client):
    response = client.post(
        '/forgot_password',
        data={'identifier': 'someone', 'method': 'sms'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'M\xc3\xa9todo de recupera\xc3\xa7\xc3\xa3o inv\xc3\xa1lido' in response.data

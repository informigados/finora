from datetime import date

from database.db import db
from models.finance import Finance
from models.user import User
from services.auth_service import generate_reset_password_token


def _create_user(app, username, email, password='Password123', timeout=0):
    with app.app_context():
        user = User(username=username, email=email, name=username.title())
        user.set_password(password)
        user.session_timeout_minutes = timeout
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, username, password='Password123'):
    return client.post(
        '/login',
        data={'identifier': username, 'password': password},
        follow_redirects=True,
    )


def test_login_rejects_missing_credentials(client):
    response = client.post('/login', data={'identifier': '', 'password': ''}, follow_redirects=True)

    assert response.status_code == 200
    assert b'Informe usu' in response.data


def test_login_and_register_redirect_when_authenticated(client, app):
    _create_user(app, 'loggedin', 'loggedin@example.com')
    _login(client, 'loggedin')

    login_response = client.get('/login', follow_redirects=False)
    register_response = client.get('/register', follow_redirects=False)

    assert login_response.status_code == 302
    assert login_response.headers['Location'].endswith('/dashboard')
    assert register_response.status_code == 302
    assert register_response.headers['Location'].endswith('/dashboard')


def test_forgot_password_email_flow_returns_generic_message(client, app):
    _create_user(app, 'recovermail', 'recovermail@example.com')

    response = client.post(
        '/forgot_password',
        data={'identifier': 'recovermail', 'method': 'email'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Se existir uma conta correspondente' in response.data


def test_reset_password_offline_rejects_weak_password(client, app):
    with app.app_context():
        user = User(username='offlineweak', email='offlineweak@example.com')
        user.set_password('Password123')
        user.set_recovery_key('ABCD1234EFGH5678')
        db.session.add(user)
        db.session.commit()

    response = client.post(
        '/reset_password/offline',
        data={
            'identifier': 'offlineweak',
            'recovery_key': 'ABCD1234EFGH5678',
            'new_password': 'weak',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'A nova senha deve ter ao menos' in response.data


def test_reset_password_token_rejects_weak_password(client, app):
    with app.app_context():
        user = User(username='tokenweak', email='tokenweak@example.com')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        token = generate_reset_password_token(user)

    response = client.post(
        f'/reset_password/{token}',
        data={'new_password': 'weak'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'A nova senha deve ter ao menos' in response.data


def test_profile_rejects_invalid_timeout_wrong_password_and_wrong_delete_confirmation(client, app):
    _create_user(app, 'profileedge', 'profileedge@example.com')
    _login(client, 'profileedge')

    timeout_response = client.post(
        '/profile',
        data={
            'action': 'update_info',
            'name': 'Profile Edge',
            'email': 'profileedge@example.com',
            'session_timeout_minutes': '999',
        },
        follow_redirects=True,
    )
    assert b'Tempo de sess' in timeout_response.data

    wrong_current_response = client.post(
        '/profile',
        data={
            'action': 'change_password',
            'current_password': 'wrong',
            'new_password': 'NewPassword123',
        },
        follow_redirects=True,
    )
    assert b'Senha atual incorreta' in wrong_current_response.data

    wrong_delete_response = client.post(
        '/profile',
        data={
            'action': 'delete_account',
            'confirmation': 'ERRADO',
        },
        follow_redirects=True,
    )
    assert b'Confirma' in wrong_delete_response.data


def test_refresh_session_open_session_mode_returns_open_flag(client, app):
    _create_user(app, 'opensession', 'opensession@example.com', timeout=0)
    _login(client, 'opensession')

    response = client.post('/session/refresh')

    assert response.status_code == 200
    assert response.get_json() == {'ok': True, 'open_session': True}


def test_dashboard_change_period_invalid_month_and_year_summary_redirect(client, app):
    _create_user(app, 'dashboardedge', 'dashboardedge@example.com')
    _login(client, 'dashboardedge')

    invalid_month = client.post(
        '/dashboard/change_period',
        data={'month': '13', 'year': '2026'},
        follow_redirects=True,
    )
    assert b'M\xc3\xaas inv\xc3\xa1lido selecionado' in invalid_month.data

    year_redirect = client.post(
        '/dashboard/change_period',
        data={'year': '2026'},
        follow_redirects=False,
    )
    assert year_redirect.status_code == 302
    assert year_redirect.headers['Location'].endswith('/dashboard/2026')


def test_dashboard_accepts_page_zero_as_first_page(client, app):
    user_id = _create_user(app, 'pagezero', 'pagezero@example.com')
    with app.app_context():
        db.session.add(
            Finance(
                description='Entry',
                value=10.0,
                category='Lazer',
                type='Despesa',
                status='Pago',
                due_date=date(2026, 3, 10),
                user_id=user_id,
            )
        )
        db.session.commit()

    _login(client, 'pagezero')
    response = client.get('/dashboard/2026/3?page=0', follow_redirects=True)

    assert response.status_code == 200
    assert b'Entry' in response.data


def test_entry_routes_handle_invalid_recurring_frequency_and_unauthorized_delete(client, app):
    _create_user(app, 'entryowner', 'entryowner@example.com')
    other_id = _create_user(app, 'entryother', 'entryother@example.com')

    _login(client, 'entryowner')
    add_response = client.post(
        '/entries/add',
        data={
            'description': 'Rec Entry',
            'value': '10',
            'category': 'Lazer',
            'type': 'Despesa',
            'status': 'Pago',
            'due_date': '2026-03-10',
            'is_recurring': 'on',
            'frequency': 'Bimestral',
        },
        follow_redirects=True,
    )
    assert b'Frequ\xc3\xaancia de recorr\xc3\xaancia inv\xc3\xa1lida' in add_response.data

    with app.app_context():
        foreign_entry = Finance(
            description='Foreign',
            value=20.0,
            category='Lazer',
            type='Despesa',
            status='Pago',
            due_date=date(2026, 3, 11),
            user_id=other_id,
        )
        db.session.add(foreign_entry)
        db.session.commit()
        foreign_entry_id = foreign_entry.id

    delete_response = client.post(f'/entries/delete/{foreign_entry_id}', follow_redirects=False)
    assert delete_response.status_code == 302

    with app.app_context():
        assert db.session.get(Finance, foreign_entry_id) is not None


def test_edit_entry_rejects_invalid_payload(client, app):
    user_id = _create_user(app, 'editinvalid', 'editinvalid@example.com')
    with app.app_context():
        entry = Finance(
            description='Editable',
            value=20.0,
            category='Lazer',
            type='Despesa',
            status='Pago',
            due_date=date(2026, 3, 12),
            user_id=user_id,
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    _login(client, 'editinvalid')
    response = client.post(
        f'/entries/edit/{entry_id}',
        data={
            'description': '',
            'value': '20',
            'category': 'Lazer',
            'type': 'Despesa',
            'status': 'Pago',
            'due_date': '2026-03-12',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Descri' in response.data

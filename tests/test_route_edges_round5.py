from datetime import date

from database.db import db
from models.finance import Finance
from models.user import User
from routes import auth as auth_module
from routes import entries as entries_module
from services.auth_service import generate_reset_password_token


def _create_user(app, username, email, password='Password123'):
    with app.app_context():
        user = User(username=username, email=email, name=username.title())
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, username, password='Password123'):
    return client.post(
        '/login',
        data={'identifier': username, 'password': password},
        follow_redirects=True,
    )


def test_login_success_resets_failed_attempts(client, app):
    with app.app_context():
        user = User(username='recoverlock', email='recoverlock@example.com', name='Recover Lock')
        user.set_password('Password123')
        user.failed_login_attempts = 2
        db.session.add(user)
        db.session.commit()

    response = _login(client, 'recoverlock')

    assert response.status_code == 200
    with app.app_context():
        refreshed = User.query.filter_by(username='recoverlock').first()
        assert refreshed.failed_login_attempts == 0
        assert refreshed.locked_until is None


def test_register_rejects_invalid_email_short_username_weak_password_and_duplicate(client, app):
    invalid_email = client.post(
        '/register',
        data={'email': 'invalid', 'username': 'validuser', 'name': 'Test', 'password': 'Password123'},
        follow_redirects=True,
    )
    assert b'endere\xc3\xa7o de e-mail v\xc3\xa1lido' in invalid_email.data

    short_username = client.post(
        '/register',
        data={'email': 'short@example.com', 'username': 'ab', 'name': 'Test', 'password': 'Password123'},
        follow_redirects=True,
    )
    assert b'Nome de usu\xc3\xa1rio deve ter pelo menos 3 caracteres' in short_username.data

    weak_password = client.post(
        '/register',
        data={'email': 'weak@example.com', 'username': 'weakuser', 'name': 'Test', 'password': 'weak'},
        follow_redirects=True,
    )
    assert b'A senha deve ter ao menos' in weak_password.data

    _create_user(app, 'duplicateuser', 'duplicate@example.com')
    duplicate = client.post(
        '/register',
        data={'email': 'duplicate@example.com', 'username': 'duplicateuser', 'name': 'Test', 'password': 'Password123'},
        follow_redirects=True,
    )
    assert b'j\xc3\xa1 existe' in duplicate.data


def test_logout_redirects_to_login(client, app):
    _create_user(app, 'logoutuser', 'logoutuser@example.com')
    _login(client, 'logoutuser')

    response = client.get('/logout', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')


def test_reset_password_offline_handles_commit_failure_without_invalid_data_flash(client, app, monkeypatch):
    with app.app_context():
        user = User(username='offlinefail', email='offlinefail@example.com')
        user.set_password('Password123')
        user.set_recovery_key('ABCD1234EFGH5678')
        db.session.add(user)
        db.session.commit()

    monkeypatch.setattr(db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    response = client.post(
        '/reset_password/offline',
        data={
            'identifier': 'offlinefail',
            'recovery_key': 'ABCD1234EFGH5678',
            'new_password': 'NewPassword123',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'N\xc3\xa3o foi poss\xc3\xadvel atualizar a senha' in response.data
    assert b'Dados de recupera\xc3\xa7\xc3\xa3o inv\xc3\xa1lidos' not in response.data


def test_reset_password_token_handles_expired_and_commit_failure(client, app, monkeypatch):
    original_resolver = auth_module.resolve_user_from_reset_token
    monkeypatch.setattr(auth_module, 'resolve_user_from_reset_token', lambda _token: (None, 'expired'))
    expired_response = client.get('/reset_password/token-expirado', follow_redirects=True)
    assert b'link de recupera\xc3\xa7\xc3\xa3o expirou' in expired_response.data.lower()

    with app.app_context():
        user = User(username='tokenfail', email='tokenfail@example.com')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        token = generate_reset_password_token(user)

    monkeypatch.setattr(auth_module, 'resolve_user_from_reset_token', original_resolver)
    monkeypatch.setattr(db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    failure_response = client.post(
        f'/reset_password/{token}',
        data={'new_password': 'BetterPass123'},
        follow_redirects=True,
    )

    assert failure_response.status_code == 200
    assert b'N\xc3\xa3o foi poss\xc3\xadvel atualizar a senha' in failure_response.data


def test_profile_route_surfaces_image_related_errors(client, app, monkeypatch):
    _create_user(app, 'imagebranch', 'imagebranch@example.com')
    _login(client, 'imagebranch')

    monkeypatch.setattr(auth_module, 'apply_profile_update', lambda **_kwargs: 'image_too_large')
    too_large = client.post('/profile', data={'action': 'update_info'}, follow_redirects=True)
    assert b'excede o tamanho m\xc3\xa1ximo permitido' in too_large.data

    monkeypatch.setattr(auth_module, 'apply_profile_update', lambda **_kwargs: 'invalid_image_name')
    invalid_name = client.post('/profile', data={'action': 'update_info'}, follow_redirects=True)
    assert b'Nome de arquivo inv\xc3\xa1lido' in invalid_name.data

    monkeypatch.setattr(auth_module, 'apply_profile_update', lambda **_kwargs: 'invalid_image')
    invalid_image = client.post('/profile', data={'action': 'update_info'}, follow_redirects=True)
    assert b'Arquivo de imagem inv\xc3\xa1lido' in invalid_image.data

    monkeypatch.setattr(auth_module, 'apply_profile_update', lambda **_kwargs: 'profile_persist_failed')
    persist_failure = client.post('/profile', data={'action': 'update_info'}, follow_redirects=True)
    assert b'N\xc3\xa3o foi poss\xc3\xadvel atualizar o perfil' in persist_failure.data


def test_profile_change_password_weak_password_branch(client, app):
    _create_user(app, 'weakbranch', 'weakbranch@example.com')
    _login(client, 'weakbranch')

    response = client.post(
        '/profile',
        data={'action': 'change_password', 'current_password': 'Password123', 'new_password': 'weak'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'A nova senha deve ter ao menos' in response.data


def test_add_entry_success_and_error_branches(client, app, monkeypatch):
    _create_user(app, 'entryaddbranches', 'entryaddbranches@example.com')
    _login(client, 'entryaddbranches')

    success_response = client.post(
        '/entries/add',
        data={
            'description': 'Compra',
            'value': '30',
            'category': 'Lazer',
            'type': 'Despesa',
            'status': 'Pago',
            'due_date': '2026-03-10',
        },
        follow_redirects=True,
    )
    assert b'Lan\xc3\xa7amento adicionado com sucesso' in success_response.data

    validation_response = client.post(
        '/entries/add',
        data={
            'description': '',
            'value': '30',
            'category': 'Lazer',
            'type': 'Despesa',
            'status': 'Pago',
            'due_date': '2026-03-10',
        },
        follow_redirects=True,
    )
    assert b'Descri\xc3\xa7\xc3\xa3o' in validation_response.data

    monkeypatch.setattr(entries_module, 'parse_finance_form', lambda _data: (_ for _ in ()).throw(RuntimeError('boom')))
    error_response = client.post(
        '/entries/add',
        data={
            'description': 'Compra',
            'value': '30',
            'category': 'Lazer',
            'type': 'Despesa',
            'status': 'Pago',
            'due_date': '2026-03-10',
        },
        follow_redirects=True,
    )
    assert b'Erro ao adicionar lan\xc3\xa7amento' in error_response.data


def test_entry_delete_and_edit_handle_commit_failures(client, app, monkeypatch):
    user_id = _create_user(app, 'entrycommitfail', 'entrycommitfail@example.com')
    with app.app_context():
        first = Finance(
            description='Delete Fail',
            value=10.0,
            category='Lazer',
            type='Despesa',
            status='Pago',
            due_date=date(2026, 3, 11),
            user_id=user_id,
        )
        second = Finance(
            description='Edit Fail',
            value=20.0,
            category='Lazer',
            type='Despesa',
            status='Pago',
            due_date=date(2026, 3, 12),
            user_id=user_id,
        )
        db.session.add_all([first, second])
        db.session.commit()
        delete_id = first.id
        edit_id = second.id

    _login(client, 'entrycommitfail')

    monkeypatch.setattr(db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    delete_response = client.post(f'/entries/delete/{delete_id}', follow_redirects=True)
    assert b'Erro ao excluir lan\xc3\xa7amento' in delete_response.data

    edit_response = client.post(
        f'/entries/edit/{edit_id}',
        data={
            'description': 'Atualizado',
            'value': '25',
            'category': 'Lazer',
            'type': 'Despesa',
            'status': 'Pago',
            'due_date': '2026-03-12',
        },
        follow_redirects=True,
    )
    assert b'Erro ao atualizar lan\xc3\xa7amento' in edit_response.data

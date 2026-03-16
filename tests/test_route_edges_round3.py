import time

from sqlalchemy.exc import IntegrityError

from app import create_app
from database.db import db
from models.audit import UserSession
from models.user import User
from routes import auth as auth_module
from routes import backup as backup_module


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


def test_secure_requests_receive_hsts_header(client, app):
    app.config['SESSION_COOKIE_SECURE'] = True

    response = client.get('/', base_url='https://finora.example')

    assert response.status_code == 200
    assert response.headers['Strict-Transport-Security'] == 'max-age=31536000; includeSubDomains'


def test_favicon_redirects_to_versioned_asset(client):
    response = client.get('/favicon.ico', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/static/favicon.svg?v=20260302e')


def test_session_timeout_redirects_to_login_when_inactive(client, app):
    _create_user(app, 'expireduser', 'expired@example.com', timeout=1)
    _login(client, 'expireduser')

    with client.session_transaction() as session:
        session['last_activity_ts'] = int(time.time()) - 120

    response = client.get('/dashboard', follow_redirects=True)

    assert response.status_code == 200
    assert b'Sess\xc3\xa3o expirada por inatividade' in response.data
    assert b'Usu\xc3\xa1rio ou e-mail' in response.data

    with app.app_context():
        session_entry = UserSession.query.first()
        assert session_entry is not None
        assert session_entry.is_current is False
        assert session_entry.ended_reason == 'timeout'


def test_register_handles_integrity_error_gracefully(client, monkeypatch):
    monkeypatch.setattr(
        db.session,
        'commit',
        lambda: (_ for _ in ()).throw(IntegrityError('stmt', 'params', 'orig')),
    )

    response = client.post(
        '/register',
        data={
            'email': 'registerfail@example.com',
            'username': 'registerfail',
            'name': 'Register Fail',
            'password': 'Password123',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'N\xc3\xa3o foi poss\xc3\xadvel concluir o cadastro' in response.data


def test_profile_delete_failure_does_not_show_wrong_confirmation_flash(client, app, monkeypatch):
    _create_user(app, 'deletefailroute', 'deletefailroute@example.com')
    _login(client, 'deletefailroute')
    monkeypatch.setattr(auth_module, 'delete_user_account', lambda *_args, **_kwargs: 'delete_account_failed')

    response = client.post(
        '/profile',
        data={'action': 'delete_account', 'confirmation': 'EXCLUIR'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'N\xc3\xa3o foi poss\xc3\xadvel excluir a conta' in response.data
    assert b'Confirma\xc3\xa7\xc3\xa3o incorreta para exclus\xc3\xa3o de conta' not in response.data


def test_backup_download_rejects_in_memory_sqlite(auth_client):
    response = auth_client.get('/backup/download', follow_redirects=True)

    assert response.status_code == 200
    assert b'Banco de dados SQLite inv\xc3\xa1lido para backup' in response.data


def test_backup_download_handles_snapshot_failure(tmp_path, monkeypatch):
    db_path = tmp_path / 'backup-failure.db'
    app = create_app('development')
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path.as_posix()}",
        ENABLE_RECURRING_SCHEDULER=False,
    )

    with app.app_context():
        db.drop_all()
        db.create_all()
        user = User(username='backupfailure', email='backupfailure@example.com', name='Backup Failure')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    client = app.test_client()
    _login(client, 'backupfailure')
    monkeypatch.setattr(
        backup_module,
        'create_backup_for_user',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('boom')),
    )

    response = client.get('/backup/download', follow_redirects=True)

    assert response.status_code == 200
    assert b'Erro ao gerar backup. Tente novamente.' in response.data

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()

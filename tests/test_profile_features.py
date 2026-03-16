from models.user import User
from models.audit import ActivityLog, UserSession
from database.db import db
from routes import auth as auth_module

def test_profile_update_email_success(client, app):
    """Test updating email successfully"""
    # Setup user
    with app.app_context():
        user = User(username='emailtest', email='old@example.com', name='Email Test')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    # Login
    client.post('/login', data={
        'identifier': 'emailtest',
        'password': 'Password123'
    }, follow_redirects=True)

    # Update Email
    response = client.post('/profile', data={
        'action': 'update_info',
        'name': 'Email Test',
        'email': 'new@example.com'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Perfil atualizado com sucesso' in response.data

    # Verify in DB
    with app.app_context():
        user = User.query.filter_by(username='emailtest').first()
        assert user.email == 'new@example.com'

def test_profile_update_email_invalid(client, app):
    """Test updating with invalid email format"""
    with app.app_context():
        user = User(username='invalidemail', email='valid@example.com', name='Test')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'invalidemail', 'password': 'Password123'}, follow_redirects=True)

    response = client.post('/profile', data={
        'action': 'update_info',
        'name': 'Test',
        'email': 'not-an-email'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Por favor, insira um endere' in response.data

def test_profile_update_email_duplicate(client, app):
    """Test updating to an email already in use"""
    with app.app_context():
        user1 = User(username='userA', email='usera@example.com', name='User A')
        user1.set_password('Pass1234')
        user2 = User(username='userB', email='userb@example.com', name='User B')
        user2.set_password('Pass1234')
        db.session.add_all([user1, user2])
        db.session.commit()

    client.post('/login', data={'identifier': 'userA', 'password': 'Pass1234'}, follow_redirects=True)

    response = client.post('/profile', data={
        'action': 'update_info',
        'name': 'User A',
        'email': 'userb@example.com' # Trying to take User B's email
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Este endere' in response.data

def test_profile_delete_photo(client, app):
    """Test deleting profile photo (resetting to default)"""
    with app.app_context():
        user = User(username='phototest', email='photo@example.com', name='Photo Test')
        user.set_password('Password123')
        user.profile_image = 'custom_pic.jpg'
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'phototest', 'password': 'Password123'}, follow_redirects=True)

    # Verify initial state
    with app.app_context():
        u = User.query.filter_by(username='phototest').first()
        assert u.profile_image == 'custom_pic.jpg'

    # Request deletion
    response = client.post('/profile', data={
        'action': 'update_info',
        'name': 'Photo Test',
        'email': 'photo@example.com',
        'delete_image': 'on'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Perfil atualizado com sucesso' in response.data

    # Verify reset
    with app.app_context():
        u = User.query.filter_by(username='phototest').first()
        assert u.profile_image == 'default_profile.svg'


def test_profile_update_session_timeout(client, app):
    with app.app_context():
        user = User(username='sessiontest', email='session@example.com', name='Session Test')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'sessiontest', 'password': 'Password123'}, follow_redirects=True)

    response = client.post('/profile', data={
        'action': 'update_info',
        'name': 'Session Test',
        'email': 'session@example.com',
        'session_timeout_minutes': '5',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Perfil atualizado com sucesso' in response.data

    with app.app_context():
        user = User.query.filter_by(username='sessiontest').first()
        assert user.session_timeout_minutes == 5


def test_refresh_session_endpoint(client, app):
    with app.app_context():
        user = User(username='refreshsession', email='refresh@example.com', name='Refresh Session')
        user.set_password('Password123')
        user.session_timeout_minutes = 1
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'refreshsession', 'password': 'Password123'}, follow_redirects=True)
    response = client.post('/session/refresh')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ok'] is True
    assert 'expires_at' in payload


def test_refresh_session_requires_auth(client):
    response = client.post('/session/refresh')
    assert response.status_code == 401
    payload = response.get_json()
    assert payload['ok'] is False


def test_profile_change_password_success(client, app):
    with app.app_context():
        user = User(username='changepass', email='changepass@example.com', name='Change Pass')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'changepass', 'password': 'Password123'}, follow_redirects=True)

    response = client.post('/profile', data={
        'action': 'change_password',
        'current_password': 'Password123',
        'new_password': 'NewPassword123',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Senha alterada com sucesso' in response.data


def test_profile_delete_account_success(client, app):
    with app.app_context():
        user = User(username='deleteacct', email='deleteacct@example.com', name='Delete Account')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'deleteacct', 'password': 'Password123'}, follow_redirects=True)
    response = client.post('/profile', data={
        'action': 'delete_account',
        'confirmation': 'EXCLUIR',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Sua conta foi exclu' in response.data

    with app.app_context():
        assert User.query.filter_by(username='deleteacct').first() is None


def test_profile_page_exposes_hub_tabs_and_support_links(client, app):
    with app.app_context():
        user = User(username='hubuser', email='hub@example.com', name='Hub User')
        user.set_password('Password123')
        user.set_recovery_key('HUBUSERKEY123456')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'hubuser', 'password': 'Password123'}, follow_redirects=True)
    response = client.get('/profile')

    assert response.status_code == 200
    assert b'Meus Backups' in response.data
    assert b'Sess' in response.data
    assert b'Status do Sistema' in response.data
    assert b'mailto:contato@informigados.com.br' in response.data
    assert b'Chave atual' in response.data
    assert b'HUBUSERKEY123456' in response.data
    assert b'Enviar por e-mail' in response.data
    assert b'Gerar nova chave' in response.data


def test_login_creates_session_history_and_activity_log(client, app):
    with app.app_context():
        user = User(username='auditlogin', email='auditlogin@example.com', name='Audit Login')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client.post('/login', data={'identifier': 'auditlogin', 'password': 'Password123'}, follow_redirects=True)

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.last_login_at is not None
        assert UserSession.query.filter_by(user_id=user_id, is_current=True).count() == 1
        assert ActivityLog.query.filter_by(user_id=user_id, event_type='login_success').count() == 1


def test_logout_closes_current_session(client, app):
    with app.app_context():
        user = User(username='auditlogout', email='auditlogout@example.com', name='Audit Logout')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client.post('/login', data={'identifier': 'auditlogout', 'password': 'Password123'}, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    with app.app_context():
        session_entry = UserSession.query.filter_by(user_id=user_id).first()
        assert session_entry is not None
        assert session_entry.is_current is False
        assert session_entry.ended_reason == 'logout'
        assert ActivityLog.query.filter_by(user_id=user_id, event_type='logout').count() == 1


def test_profile_recovery_key_email_action_updates_timestamp_and_activity(client, app, monkeypatch):
    with app.app_context():
        user = User(username='recoverysend', email='recoverysend@example.com', name='Recovery Send')
        user.set_password('Password123')
        user.set_recovery_key('RECOVERYSEND1234')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    def fake_send_recovery_key_email(user, recovery_key, reason):
        assert recovery_key == 'RECOVERYSEND1234'
        assert reason == 'resend'
        user.mark_recovery_key_sent()
        db.session.commit()
        return {'ok': True, 'delivery': 'smtp'}

    monkeypatch.setattr(auth_module, 'send_recovery_key_email', fake_send_recovery_key_email)

    client.post('/login', data={'identifier': 'recoverysend', 'password': 'Password123'}, follow_redirects=True)
    response = client.post('/profile', data={'action': 'email_recovery_key'}, follow_redirects=True)

    assert response.status_code == 200
    assert b'Chave de recupera' in response.data

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.recovery_key_last_sent_at is not None
        assert ActivityLog.query.filter_by(user_id=user_id, event_type='recovery_key_emailed').count() == 1


def test_profile_recovery_key_email_action_warns_when_current_key_is_unavailable(client, app):
    with app.app_context():
        user = User(username='recoverymissing', email='recoverymissing@example.com', name='Recovery Missing')
        user.set_password('Password123')
        user.set_recovery_key('RECOVERYMISS1234')
        user.recovery_key_ciphertext = None
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'recoverymissing', 'password': 'Password123'}, follow_redirects=True)
    response = client.post('/profile', data={'action': 'email_recovery_key'}, follow_redirects=True)

    assert response.status_code == 200
    assert b'n\xc3\xa3o est\xc3\xa1 dispon\xc3\xadvel para reenvio' in response.data.lower()


def test_profile_recovery_key_regenerate_replaces_key_and_records_activity(client, app, monkeypatch):
    with app.app_context():
        user = User(username='recoveryregen', email='recoveryregen@example.com', name='Recovery Regen')
        user.set_password('Password123')
        user.set_recovery_key('OLDRECOVERYKEY12')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        previous_version = user.recovery_key_version

    monkeypatch.setattr(auth_module, 'generate_recovery_key', lambda: 'NEWRECOVERYKEY12')

    def fake_send_recovery_key_email(user, recovery_key, reason):
        assert recovery_key == 'NEWRECOVERYKEY12'
        assert reason == 'regenerate'
        user.mark_recovery_key_sent()
        db.session.commit()
        return {'ok': True, 'delivery': 'smtp'}

    monkeypatch.setattr(auth_module, 'send_recovery_key_email', fake_send_recovery_key_email)

    client.post('/login', data={'identifier': 'recoveryregen', 'password': 'Password123'}, follow_redirects=True)
    response = client.post('/profile', data={'action': 'regenerate_recovery_key'}, follow_redirects=True)

    assert response.status_code == 200
    assert b'NEWRECOVERYKEY12' in response.data

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.get_recovery_key() == 'NEWRECOVERYKEY12'
        assert user.check_recovery_key('NEWRECOVERYKEY12') is True
        assert user.recovery_key_version == previous_version + 1
        assert user.recovery_key_last_sent_at is not None
        assert ActivityLog.query.filter_by(user_id=user_id, event_type='recovery_key_regenerated').count() == 1

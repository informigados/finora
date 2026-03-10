
import pytest
from models.user import User
from database.db import db

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

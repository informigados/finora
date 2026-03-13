import pytest
from app import create_app
from database.db import db
from models.user import User

@pytest.fixture
def app():
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def auth_client(client, app):
    # Create a user
    with app.app_context():
        user = User(username='testuser', email='test@example.com', name='Test User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    # Login
    client.post('/login', data={
        'identifier': 'testuser',
        'password': 'Password123'
    }, follow_redirects=True)
    
    return client

from routes import auth as auth_module


def test_register(client):
    response = client.post('/register', data={
        'username': 'newuser',
        'email': 'new@example.com',
        'password': 'Password123',
        'name': 'New User'
    }, follow_redirects=True)
    assert response.status_code == 200
    # Check for success message (might be in toast)
    assert b'Conta criada com sucesso' in response.data


def test_register_sends_recovery_key_email_and_persists_ciphertext(client, app, monkeypatch):
    deliveries = []

    def fake_send_recovery_key_email(user, recovery_key, reason):
        deliveries.append((user.email, recovery_key, reason))
        return {'ok': True, 'delivery': 'smtp'}

    monkeypatch.setattr(auth_module, 'send_recovery_key_email', fake_send_recovery_key_email)

    response = client.post('/register', data={
        'username': 'mailregister',
        'email': 'mailregister@example.com',
        'password': 'Password123',
        'name': 'Mail Register User'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Tamb' in response.data
    assert len(deliveries) == 1
    assert deliveries[0][0] == 'mailregister@example.com'
    assert deliveries[0][2] == 'register'
    assert len(deliveries[0][1]) == 16

    with app.app_context():
        from models.user import User

        user = User.query.filter_by(username='mailregister').first()
        assert user is not None
        assert user.recovery_key_ciphertext
        assert user.get_recovery_key() == deliveries[0][1]

def test_register_invalid_email(client):
    response = client.post('/register', data={
        'username': 'invalidemailuser',
        'email': 'invalid-email',
        'password': 'Password123',
        'name': 'Invalid Email User'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Por favor, insira um endere' in response.data # Partial match for unicode safety

def test_login(client, app):
    # Register first
    with app.app_context():
        from models.user import User
        from database.db import db
        user = User(username='loginuser', email='login@example.com', name='Login User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    response = client.post('/login', data={
        'identifier': 'loginuser',
        'password': 'Password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Novo Lan' in response.data
    
def test_login_fail(client):
    response = client.post('/login', data={
        'identifier': 'wronguser',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Por favor verifique seus dados' in response.data

def test_dashboard_access_denied(client):
    response = client.get('/dashboard/2025/1', follow_redirects=True)
    assert response.status_code == 200
    # Should redirect to login. Check for login page content "Entrar"
    # Note: Flask-Babel default is 'pt' in config
    assert b'Entrar' in response.data
    assert b'password' in response.data


def test_welcome_page_before_login(client):
    response = client.get('/', follow_redirects=True)
    assert response.status_code == 200
    assert b'Bem-vindo' in response.data
    assert b'Entrar' in response.data


def test_about_page_available(client):
    response = client.get('/about', follow_redirects=True)
    assert response.status_code == 200
    assert b'Sobre o Finora' in response.data


def test_about_legacy_redirects(client):
    response = client.get('/sobre', follow_redirects=False)

    assert response.status_code == 301
    assert response.headers['Location'].endswith('/about')

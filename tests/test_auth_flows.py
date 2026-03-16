from datetime import date

from database.db import db
from models.finance import Finance
from models.user import User
from itsdangerous import URLSafeSerializer
from services.auth_service import generate_reset_password_token


def test_reset_password_token_flow_updates_password(client, app):
    with app.app_context():
        user = User(username='tokenuser', email='token@example.com', name='Token User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        token = generate_reset_password_token(user)

    response = client.post(
        f'/reset_password/{token}',
        data={'new_password': 'BetterPass123'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Sua senha foi atualizada com sucesso' in response.data

    login_response = client.post(
        '/login',
        data={'identifier': 'tokenuser', 'password': 'BetterPass123'},
        follow_redirects=True,
    )
    assert b'Novo Lan' in login_response.data


def test_reset_password_token_rejects_invalid_token(client):
    response = client.get('/reset_password/token-invalido', follow_redirects=True)

    assert response.status_code == 200
    assert b'Link de recupera' in response.data


def test_user_recovery_key_roundtrip_and_tamper_returns_none(app):
    with app.app_context():
        user = User(username='roundtripuser', email='roundtrip@example.com', name='Roundtrip User')
        user.set_password('Password123')
        user.set_recovery_key('ROUNDTRIPKEY1234')
        db.session.add(user)
        db.session.commit()

        assert user.recovery_key_salt
        assert user.get_recovery_key() == 'ROUNDTRIPKEY1234'
        assert user.check_recovery_key('ROUNDTRIPKEY1234') is True

        user.recovery_key_ciphertext = 'tampered'
        db.session.commit()
        assert user.get_recovery_key() is None


def test_user_recovery_key_reads_legacy_signed_payload(app):
    with app.app_context():
        user = User(username='legacyrecovery', email='legacyrecovery@example.com', name='Legacy Recovery')
        user.set_password('Password123')
        serializer = URLSafeSerializer(app.config['SECRET_KEY'], salt='finora-recovery-key')
        user.recovery_key_ciphertext = serializer.dumps({'key': 'LEGACYRECOVERY12'})
        db.session.add(user)
        db.session.commit()

        assert user.get_recovery_key() == 'LEGACYRECOVERY12'


def test_user_recovery_key_reads_legacy_encrypted_payload_without_user_salt(app):
    with app.app_context():
        user = User(username='legacyenc', email='legacyenc@example.com', name='Legacy Enc')
        user.set_password('Password123')
        user.recovery_key_ciphertext = User._serialize_recovery_key('LEGACYENCODED12')
        user.recovery_key_salt = None
        db.session.add(user)
        db.session.commit()

        assert user.get_recovery_key() == 'LEGACYENCODED12'


def test_profile_visit_rewraps_legacy_recovery_key_storage(client, app):
    with app.app_context():
        user = User(username='rewraplegacy', email='rewraplegacy@example.com', name='Rewrap Legacy')
        user.set_password('Password123')
        serializer = URLSafeSerializer(app.config['SECRET_KEY'], salt='finora-recovery-key')
        user.recovery_key_ciphertext = serializer.dumps({'key': 'LEGACYPROFILE123'})
        user.recovery_key_salt = None
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'rewraplegacy', 'password': 'Password123'}, follow_redirects=True)
    response = client.get('/profile')

    assert response.status_code == 200

    with app.app_context():
        refreshed = User.query.filter_by(username='rewraplegacy').first()
        assert refreshed.recovery_key_salt
        assert refreshed.recovery_key_ciphertext.startswith('enc:')
        assert refreshed.get_recovery_key() == 'LEGACYPROFILE123'


def test_dashboard_redirects_when_page_exceeds_total(client, app):
    with app.app_context():
        user = User(username='pageuser', email='page@example.com', name='Page User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        entry = Finance(
            description='Only Entry',
            value=10.0,
            category='Lazer',
            type='Despesa',
            status='Pago',
            due_date=date(2026, 3, 10),
            user_id=user.id,
        )
        db.session.add(entry)
        db.session.commit()

    client.post('/login', data={'identifier': 'pageuser', 'password': 'Password123'}, follow_redirects=True)
    response = client.get('/dashboard/2026/3?page=999', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/dashboard/2026/3?page=1')


def test_year_dashboard_is_scoped_to_authenticated_user(client, app):
    with app.app_context():
        user = User(username='yearuser', email='year@example.com', name='Year User')
        user.set_password('Password123')
        other = User(username='otheryear', email='otheryear@example.com', name='Other Year')
        other.set_password('Password123')
        db.session.add_all([user, other])
        db.session.commit()

        db.session.add_all([
            Finance(
                description='User Income',
                value=500.0,
                category='Salário',
                type='Receita',
                status='Pago',
                due_date=date(2026, 1, 5),
                user_id=user.id,
            ),
            Finance(
                description='Other Income',
                value=900.0,
                category='Salário',
                type='Receita',
                status='Pago',
                due_date=date(2026, 1, 5),
                user_id=other.id,
            ),
        ])
        db.session.commit()

    client.post('/login', data={'identifier': 'yearuser', 'password': 'Password123'}, follow_redirects=True)
    response = client.get('/dashboard/2026', follow_redirects=True)

    assert response.status_code == 200
    assert b'500.00' in response.data
    assert b'900.00' not in response.data


def test_reset_password_token_is_invalidated_after_successful_use(client, app):
    with app.app_context():
        user = User(username='reusetokenuser', email='reusetoken@example.com', name='Reuse Token User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        token = generate_reset_password_token(user)

    first_response = client.post(
        f'/reset_password/{token}',
        data={'new_password': 'BetterPass123'},
        follow_redirects=True,
    )
    assert first_response.status_code == 200
    assert b'Sua senha foi atualizada com sucesso' in first_response.data

    second_response = client.get(
        f'/reset_password/{token}',
        follow_redirects=True,
    )
    assert second_response.status_code == 200
    assert b'Link de recupera' in second_response.data

    with app.app_context():
        refreshed_user = User.query.filter_by(username='reusetokenuser').first()
        assert refreshed_user.password_reset_token_hash


def test_profile_password_change_increments_reset_token_version(client, app):
    with app.app_context():
        user = User(username='versionedreset', email='versionedreset@example.com', name='Versioned Reset')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        token = generate_reset_password_token(user)

    client.post('/login', data={'identifier': 'versionedreset', 'password': 'Password123'}, follow_redirects=True)
    response = client.post(
        '/profile',
        data={
            'action': 'change_password',
            'current_password': 'Password123',
            'new_password': 'BetterPass123',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Senha alterada com sucesso' in response.data

    expired_token_response = client.get(f'/reset_password/{token}', follow_redirects=True)
    assert expired_token_response.status_code == 200
    assert b'Link de recupera' in expired_token_response.data

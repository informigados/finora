from datetime import date

from database.db import db
from models.finance import Finance
from models.user import User
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

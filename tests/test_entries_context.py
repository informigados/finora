from datetime import date

from database.db import db
from models.finance import Finance
from models.user import User


def _create_logged_user(client, app, username, email):
    with app.app_context():
        user = User(username=username, email=email, name='Entry User')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client.post('/login', data={'identifier': username, 'password': 'Pass1234'}, follow_redirects=True)
    return user_id


def test_edit_entry_preserves_dashboard_context(client, app):
    user_id = _create_logged_user(client, app, 'entryedit', 'entryedit@example.com')

    with app.app_context():
        entry = Finance(
            description='Old',
            value=10.0,
            category='Lazer',
            type='Despesa',
            status='Pendente',
            due_date=date(2025, 1, 15),
            user_id=user_id,
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    response = client.post(f'/entries/edit/{entry_id}', data={
        'description': 'Updated',
        'value': '12.5',
        'category': 'Lazer',
        'type': 'Despesa',
        'status': 'Pago',
        'due_date': '2025-01-20',
        'payment_date': '2025-01-20',
        'observations': '',
        'redirect_year': '2025',
        'redirect_month': '1',
        'redirect_page': '2',
    }, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/dashboard/2025/1?page=2')


def test_delete_entry_preserves_dashboard_context(client, app):
    user_id = _create_logged_user(client, app, 'entrydelete', 'entrydelete@example.com')

    with app.app_context():
        entry = Finance(
            description='Delete me',
            value=20.0,
            category='Lazer',
            type='Despesa',
            status='Pendente',
            due_date=date(2025, 1, 10),
            user_id=user_id,
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    response = client.post(f'/entries/delete/{entry_id}', data={
        'redirect_year': '2025',
        'redirect_month': '1',
        'redirect_page': '3',
    }, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/dashboard/2025/1?page=3')

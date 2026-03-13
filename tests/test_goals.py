from models.goal import Goal
from models.user import User
from database.db import db


def test_add_goal_rejects_empty_name(client, app):
    with app.app_context():
        user = User(username='goaluser', email='goal@example.com', name='Goal User')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'goaluser', 'password': 'Pass1234'}, follow_redirects=True)

    response = client.post('/goals/add', data={
        'name': '   ',
        'target_amount': '1000',
        'current_amount': '0',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Nome da meta' in response.data

    with app.app_context():
        assert Goal.query.count() == 0


def test_add_goal_success(client, app):
    with app.app_context():
        user = User(username='goalok', email='goalok@example.com', name='Goal Ok')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'goalok', 'password': 'Pass1234'}, follow_redirects=True)
    response = client.post('/goals/add', data={
        'name': 'Reserva de Emergência',
        'target_amount': '2000',
        'current_amount': '150',
        'deadline': '2026-12-31',
    }, follow_redirects=True)

    assert response.status_code == 200

    with app.app_context():
        goal = Goal.query.filter_by(name='Reserva de Emergência').first()
        assert goal is not None
        assert goal.current_amount == 150


def test_add_goal_rejects_invalid_amounts(client, app):
    with app.app_context():
        user = User(username='goalinvalid', email='goalinvalid@example.com', name='Goal Invalid')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'goalinvalid', 'password': 'Pass1234'}, follow_redirects=True)
    response = client.post('/goals/add', data={
        'name': 'Meta inválida',
        'target_amount': '-1',
        'current_amount': '0',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'valores da meta' in response.data

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

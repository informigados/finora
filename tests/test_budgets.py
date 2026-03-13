from models.budget import Budget
from models.finance import Finance
from services.budget_service import get_budget_status
from datetime import datetime

def test_add_budget(client, app):
    # Setup user
    with app.app_context():
        from models.user import User
        from database.db import db
        user = User(username='buduser', email='bud@example.com', name='Bud User')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()
        
    client.post('/login', data={'identifier': 'buduser', 'password': 'Pass1234'}, follow_redirects=True)
    
    response = client.post('/budgets/add', data={
        'category': 'Lazer',
        'limit_amount': '500.00',
        'period': 'Mensal'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'com sucesso' in response.data

    with app.app_context():
        bud = Budget.query.first()
        assert bud.limit_amount == 500.0

def test_budget_calculation(app):
    with app.app_context():
        from models.user import User
        from database.db import db
        user = User(username='calcuser', email='calc@example.com', name='Calc User')
        db.session.add(user)
        db.session.commit()
        
        # Budget 100
        bud = Budget(category='Lazer', limit_amount=100.0, period='Mensal', user_id=user.id)
        db.session.add(bud)
        
        # Expense 60
        today = datetime.now().date()
        fin = Finance(
            description='Game', value=60.0, category='Lazer', type='Despesa', 
            due_date=today, user_id=user.id
        )
        db.session.add(fin)
        db.session.commit()
        
        status = get_budget_status(user.id, today.month, today.year)
        
        assert len(status) == 1
        assert status[0]['spent'] == 60.0
        assert status[0]['remaining'] == 40.0
        assert status[0]['percentage'] == 60.0


def test_add_budget_rejects_invalid_limit_and_period(client, app):
    with app.app_context():
        from models.user import User
        from database.db import db
        user = User(username='budinvalid', email='budinvalid@example.com', name='Bud Invalid')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'budinvalid', 'password': 'Pass1234'}, follow_redirects=True)

    limit_response = client.post('/budgets/add', data={
        'category': 'Lazer',
        'limit_amount': '0',
        'period': 'Mensal'
    }, follow_redirects=True)
    assert b'maior que zero' in limit_response.data

    period_response = client.post('/budgets/add', data={
        'category': 'Lazer',
        'limit_amount': '100',
        'period': 'Semestral'
    }, follow_redirects=True)
    assert b'Per\xc3\xadodo de or\xc3\xa7amento inv\xc3\xa1lido' in period_response.data

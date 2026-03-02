from models.recurring import RecurringEntry
from models.finance import Finance
from services.recurring_service import process_recurring_entries
from datetime import datetime, timedelta

def test_add_recurring_entry(client, app):
    with app.app_context():
        from models.user import User
        from database.db import db
        user = User(username='recuser', email='rec@example.com', name='Rec User')
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
    
    client.post('/login', data={'identifier': 'recuser', 'password': 'pass'}, follow_redirects=True)
    
    today = datetime.now().strftime('%Y-%m-%d')
    response = client.post('/entries/add', data={
        'description': 'Test Recurring',
        'value': '100.00',
        'category': 'Lazer',
        'type': 'Despesa',
        'status': 'Pendente',
        'due_date': today,
        'is_recurring': 'on',
        'frequency': 'Mensal'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Check for success message (utf-8 bytes for 'recorrência')
    # "Lançamento e recorrência adicionados com sucesso!"
    assert b'recorr\xc3\xaancia adicionados' in response.data

    with app.app_context():
        rec = RecurringEntry.query.first()
        assert rec is not None
        assert rec.frequency == 'Mensal'
        # Next run date should be next month (roughly)
        assert rec.next_run_date > datetime.now().date()

def test_process_recurring(app):
    with app.app_context():
        from models.user import User
        from database.db import db
        user = User(username='procuser', email='proc@example.com', name='Proc User')
        db.session.add(user)
        db.session.commit()
        
        today = datetime.now().date()
        rec = RecurringEntry(
            description='Due Entry',
            value=50.0,
            category='Lazer',
            type='Despesa',
            frequency='Diário',
            start_date=today - timedelta(days=1),
            next_run_date=today, # DUE TODAY
            user_id=user.id
        )
        db.session.add(rec)
        db.session.commit()
        
        # Run process
        count = process_recurring_entries(user.id)
        assert count == 1
        
        # Check if Finance entry created
        finance = Finance.query.filter_by(description='Due Entry').first()
        assert finance is not None
        
        # Check if next_run_date updated
        db.session.refresh(rec)
        assert rec.next_run_date == today + timedelta(days=1)

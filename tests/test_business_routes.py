from datetime import date, timedelta

from app import create_app
from database.db import db
from models.budget import Budget
from models.finance import Finance
from models.goal import Goal
from models.recurring import RecurringEntry
from models.user import User
from services import maintenance_service
from services.maintenance_service import run_recurring_maintenance, start_recurring_scheduler
from services.reports import generate_pdf_report


def _login_user(client, username, password='Pass1234'):
    return client.post(
        '/login',
        data={'identifier': username, 'password': password},
        follow_redirects=True,
    )


def test_edit_and_delete_budget_flow(client, app):
    with app.app_context():
        user = User(username='budgetowner', email='budgetowner@example.com', name='Budget Owner')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

        budget = Budget(category='Lazer', limit_amount=500.0, period='Mensal', user_id=user.id)
        db.session.add(budget)
        db.session.commit()
        budget_id = budget.id

    _login_user(client, 'budgetowner')

    edit_response = client.post(
        f'/budgets/edit/{budget_id}',
        data={'limit_amount': '650.0', 'period': 'Anual'},
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    assert b'Or\xc3\xa7amento atualizado' in edit_response.data

    with app.app_context():
        updated_budget = db.session.get(Budget, budget_id)
        assert updated_budget.limit_amount == 650.0
        assert updated_budget.period == 'Anual'

    delete_response = client.post(f'/budgets/delete/{budget_id}', follow_redirects=True)
    assert delete_response.status_code == 200
    assert b'Or\xc3\xa7amento removido' in delete_response.data

    with app.app_context():
        assert db.session.get(Budget, budget_id) is None


def test_add_budget_rejects_duplicate_category_period(client, app):
    with app.app_context():
        user = User(username='budgetdup', email='budgetdup@example.com', name='Budget Dup')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

        budget = Budget(category='Lazer', limit_amount=300.0, period='Mensal', user_id=user.id)
        db.session.add(budget)
        db.session.commit()

    _login_user(client, 'budgetdup')
    response = client.post(
        '/budgets/add',
        data={'category': 'Lazer', 'limit_amount': '400', 'period': 'Mensal'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'J\xc3\xa1 existe um or\xc3\xa7amento' in response.data


def test_goal_update_and_delete_flow(client, app):
    with app.app_context():
        user = User(username='goalowner', email='goalowner@example.com', name='Goal Owner')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

        goal = Goal(name='Reserva', target_amount=1000.0, current_amount=100.0, user_id=user.id)
        db.session.add(goal)
        db.session.commit()
        goal_id = goal.id

    _login_user(client, 'goalowner')

    update_response = client.post(
        f'/goals/update/{goal_id}',
        data={'current_amount': '450.0'},
        follow_redirects=True,
    )
    assert update_response.status_code == 200
    assert b'Meta atualizada com sucesso' in update_response.data

    with app.app_context():
        updated_goal = db.session.get(Goal, goal_id)
        assert updated_goal.current_amount == 450.0

    delete_response = client.post(f'/goals/delete/{goal_id}', follow_redirects=True)
    assert delete_response.status_code == 200
    assert b'Meta removida com sucesso' in delete_response.data

    with app.app_context():
        assert db.session.get(Goal, goal_id) is None


def test_goal_update_rejects_negative_amount(client, app):
    with app.app_context():
        user = User(username='goalnegative', email='goalnegative@example.com', name='Goal Negative')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

        goal = Goal(name='Viagem', target_amount=1000.0, current_amount=100.0, user_id=user.id)
        db.session.add(goal)
        db.session.commit()
        goal_id = goal.id

    _login_user(client, 'goalnegative')
    response = client.post(
        f'/goals/update/{goal_id}',
        data={'current_amount': '-10'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'n\xc3\xa3o pode ser negativo' in response.data


def test_export_txt_and_pdf(client, app):
    with app.app_context():
        user = User(username='exportowner', email='exportowner@example.com', name='Export Owner')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

        entry = Finance(
            description='Aluguel',
            value=1200.0,
            category='Moradia',
            type='Despesa',
            status='Pago',
            due_date=date(2026, 3, 5),
            user_id=user.id,
        )
        db.session.add(entry)
        db.session.commit()

    _login_user(client, 'exportowner')

    txt_response = client.get('/export/txt/2026/3')
    assert txt_response.status_code == 200
    assert txt_response.mimetype == 'text/plain'
    assert 'Relatório FINORA' in txt_response.get_data(as_text=True)

    pdf_response = client.get('/export/pdf/2026/3')
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == 'application/pdf'
    assert pdf_response.data.startswith(b'%PDF')


def test_generate_pdf_report_returns_pdf_bytes():
    finances = [
        Finance(
            description='Descricao muito longa para ser truncada corretamente no relatório PDF',
            value=123.45,
            category='Categoria muito longa para testar truncamento',
            type='Despesa',
            status='Pago',
            due_date=date(2026, 3, 1),
        )
    ]
    stats = {
        'total_receitas': 0.0,
        'total_despesas': 123.45,
        'total_geral': -123.45,
        'total_pago': 123.45,
        'total_pendente': 0.0,
        'total_atrasado': 0.0,
    }

    pdf_bytes = generate_pdf_report(3, 2026, finances, stats)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b'%PDF')


def test_run_recurring_maintenance_processes_due_entries(app):
    with app.app_context():
        user = User(username='maintuser', email='maint@example.com', name='Maint User')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

        recurring = RecurringEntry(
            description='Maintenance Recurring',
            value=55.0,
            category='Lazer',
            type='Despesa',
            frequency='Diário',
            start_date=date.today() - timedelta(days=1),
            next_run_date=date.today(),
            user_id=user.id,
        )
        db.session.add(recurring)
        db.session.commit()

        result = run_recurring_maintenance(app)

        assert result['processed_entries'] == 1
        assert result['affected_users'] == 1
        assert Finance.query.filter_by(description='Maintenance Recurring').count() == 1


def test_run_recurring_maintenance_skips_when_schema_is_incomplete(app, monkeypatch):
    monkeypatch.setattr(maintenance_service, 'recurring_schema_is_ready', lambda: False)

    result = run_recurring_maintenance(app)

    assert result == {'processed_entries': 0, 'affected_users': 0, 'skipped': True}


def test_start_recurring_scheduler_returns_none_in_testing(app):
    assert start_recurring_scheduler(app) is None


def test_start_recurring_scheduler_skips_when_schema_is_incomplete(monkeypatch):
    app = create_app('development')
    app.config.update(TESTING=False, ENABLE_RECURRING_SCHEDULER=True)
    monkeypatch.setattr(maintenance_service, 'recurring_schema_is_ready', lambda: False)

    assert start_recurring_scheduler(app) is None


def test_backup_download_works_for_file_sqlite(tmp_path):
    db_path = tmp_path / 'backup-test.db'
    app = create_app('development')
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path.as_posix()}",
        ENABLE_RECURRING_SCHEDULER=False,
    )

    with app.app_context():
        db.drop_all()
        db.create_all()
        user = User(username='backupuser', email='backup@example.com', name='Backup User')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

    client = app.test_client()
    _login_user(client, 'backupuser')
    response = client.get('/backup/download')

    assert response.status_code == 200
    assert response.mimetype == 'application/zip'
    assert response.data[:2] == b'PK'

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()

import io
from datetime import date

from database.db import db
from models.budget import Budget
from models.finance import Finance
from models.goal import Goal
from models.user import User
from routes import imports as imports_module
from services.import_service import ImportResult


def _create_user(app, username, email, password='Pass1234'):
    with app.app_context():
        user = User(username=username, email=email, name=username.title())
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, username, password='Pass1234'):
    return client.post(
        '/login',
        data={'identifier': username, 'password': password},
        follow_redirects=True,
    )


def test_add_budget_handles_commit_failure(client, app, monkeypatch):
    _create_user(app, 'budgetcommit', 'budgetcommit@example.com')
    _login(client, 'budgetcommit')
    monkeypatch.setattr(db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('boom')))

    response = client.post(
        '/budgets/add',
        data={'category': 'Lazer', 'limit_amount': '100', 'period': 'Mensal'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Erro ao definir or\xc3\xa7amento' in response.data


def test_edit_and_delete_budget_handle_failures(client, app, monkeypatch):
    user_id = _create_user(app, 'budgeteditfail', 'budgeteditfail@example.com')
    with app.app_context():
        budget = Budget(category='Lazer', limit_amount=300.0, period='Mensal', user_id=user_id)
        db.session.add(budget)
        db.session.commit()
        budget_id = budget.id

    _login(client, 'budgeteditfail')
    invalid_limit_response = client.post(
        f'/budgets/edit/{budget_id}',
        data={'limit_amount': '0', 'period': 'Mensal'},
        follow_redirects=True,
    )
    assert b'maior que zero' in invalid_limit_response.data

    invalid_period_response = client.post(
        f'/budgets/edit/{budget_id}',
        data={'limit_amount': '100', 'period': 'Semestral'},
        follow_redirects=True,
    )
    assert b'Per\xc3\xadodo de or\xc3\xa7amento inv\xc3\xa1lido' in invalid_period_response.data

    monkeypatch.setattr(db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    delete_response = client.post(f'/budgets/delete/{budget_id}', follow_redirects=True)
    assert b'Erro ao remover or\xc3\xa7amento' in delete_response.data


def test_goal_routes_handle_add_delete_and_update_failures(client, app, monkeypatch):
    user_id = _create_user(app, 'goalfail', 'goalfail@example.com')
    with app.app_context():
        goal = Goal(name='Reserva', target_amount=1000.0, current_amount=100.0, user_id=user_id)
        db.session.add(goal)
        db.session.commit()
        goal_id = goal.id

    _login(client, 'goalfail')

    add_response = client.post(
        '/goals/add',
        data={
            'name': 'Meta com data inv\xc3\xa1lida',
            'target_amount': '1000',
            'current_amount': '100',
            'deadline': '31-12-2026',
        },
        follow_redirects=True,
    )
    assert b'Data limite inv\xc3\xa1lida' in add_response.data

    monkeypatch.setattr(db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    update_response = client.post(
        f'/goals/update/{goal_id}',
        data={'current_amount': '500'},
        follow_redirects=True,
    )
    assert b'Erro ao atualizar meta financeira' in update_response.data

    delete_response = client.post(f'/goals/delete/{goal_id}', follow_redirects=True)
    assert b'Erro ao remover meta financeira' in delete_response.data


def test_import_route_flashes_skipped_rows_summary(auth_client, monkeypatch):
    result = ImportResult(
        entries=[
            Finance(
                description='Importado',
                value=10.0,
                category='Lazer',
                type='Despesa',
                status='Pago',
                due_date=date(2026, 3, 10),
                user_id=1,
            )
        ],
        imported_rows=1,
        skipped_rows=4,
        errors=['Linha 2', 'Linha 3', 'Linha 4', 'Linha 5'],
    )
    monkeypatch.setattr(imports_module, 'import_finances_from_file', lambda **_kwargs: result)

    response = auth_client.post(
        '/import',
        data={'file': (io.BytesIO(b'dados'), 'finances.csv')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'1 lan\xc3\xa7amento(s) importado(s) com sucesso' in response.data
    assert b'e mais 1 linha(s)' in response.data


def test_import_route_warns_when_parser_returns_zero_entries(auth_client, monkeypatch):
    empty_result = ImportResult(entries=[], imported_rows=0, skipped_rows=0, errors=[])
    monkeypatch.setattr(imports_module, 'import_finances_from_file', lambda **_kwargs: empty_result)

    response = auth_client.post(
        '/import',
        data={'file': (io.BytesIO(b'data'), 'finances.csv')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Nenhum lan\xc3\xa7amento v\xc3\xa1lido foi encontrado no arquivo' in response.data

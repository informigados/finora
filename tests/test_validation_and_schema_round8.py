import io

import pytest
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import FileStorage, MultiDict

from database.db import db
from models.finance import Finance
from models.goal import Goal
from models.user import User
from services.catalogs import normalize_finance_category
from services.db_resilience import run_idempotent_db_operation
from services.import_service import ImportValidationError, import_finances_from_file
from services.validators import parse_finance_form, validate_finance_data


def test_finance_and_goal_user_id_are_non_nullable():
    assert Finance.__table__.c.user_id.nullable is False
    assert Goal.__table__.c.user_id.nullable is False


def test_validate_finance_data_rejects_unknown_category():
    errors = validate_finance_data(
        MultiDict(
            {
                'description': 'Teste',
                'value': '10',
                'category': 'CategoriaInventada',
                'type': 'Despesa',
                'status': 'Pago',
                'due_date': '2026-03-10',
            }
        )
    )

    assert 'Categoria inválida. Selecione uma categoria permitida.' in errors


def test_parse_finance_form_normalizes_allowed_category_alias():
    payload, errors = parse_finance_form(
        MultiDict(
            {
                'description': 'Salário',
                'value': '100',
                'category': 'salary',
                'type': 'Receita',
                'status': 'Pago',
                'due_date': '2026-03-10',
            }
        )
    )

    assert errors == []
    assert payload['category'] == 'Trabalho'
    assert payload['subcategory'] == 'Salário'


def test_normalize_finance_category_housing_alias():
    assert normalize_finance_category('housing') == 'Moradia'


def test_budget_route_rejects_invalid_category(client, app):
    with app.app_context():
        user = User(username='budgetinvalidcat', email='budgetinvalidcat@example.com', name='Budget Invalid Cat')
        user.set_password('Pass1234')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'budgetinvalidcat', 'password': 'Pass1234'}, follow_redirects=True)
    response = client.post(
        '/budgets/add',
        data={'category': 'OutraCategoria', 'limit_amount': '100', 'period': 'Mensal'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Categoria inv\xc3\xa1lida' in response.data


def test_import_service_normalizes_allowed_category_alias():
    csv_content = (
        'description,value,category,type,status,due_date\n'
        'Salary,5000,salary,Receita,Pago,2026-03-10\n'
    )
    uploaded = FileStorage(stream=io.BytesIO(csv_content.encode('utf-8')), filename='finances.csv')

    result = import_finances_from_file(uploaded, user_id=1)

    assert result.imported_rows == 1
    assert result.entries[0].category == 'Trabalho'
    assert result.entries[0].subcategory == 'Salário'


def test_parse_finance_form_accepts_explicit_valid_subcategory():
    payload, errors = parse_finance_form(
        MultiDict(
            {
                'description': 'Mercado',
                'value': '80',
                'category': 'Alimentação',
                'subcategory': 'Supermercado',
                'type': 'Despesa',
                'status': 'Pago',
                'due_date': '2026-03-10',
            }
        )
    )

    assert errors == []
    assert payload['category'] == 'Alimentação'
    assert payload['subcategory'] == 'Supermercado'


def test_validate_finance_data_rejects_zero_value():
    errors = validate_finance_data(
        MultiDict(
            {
                'description': 'Conta',
                'value': '0',
                'category': 'Utilidades',
                'subcategory': 'Água',
                'type': 'Despesa',
                'status': 'Pago',
                'due_date': '2026-03-10',
            }
        )
    )

    assert 'Valor deve ser maior que zero.' in errors


def test_import_service_requires_due_date():
    csv_content = (
        'description,value,category,type,status,due_date\n'
        'Salary,5000,salary,Receita,Pago,\n'
    )
    uploaded = FileStorage(stream=io.BytesIO(csv_content.encode('utf-8')), filename='finances.csv')

    with pytest.raises(ImportValidationError) as exc_info:
        import_finances_from_file(uploaded, user_id=1)

    assert 'Data de vencimento' in str(exc_info.value)


def test_run_idempotent_db_operation_retries_retryable_errors(app):
    with app.app_context():
        calls = {'count': 0}
        dummy_sql_for_retry_test = 'SELECT 1'

        def flaky_operation():
            calls['count'] += 1
            if calls['count'] == 1:
                raise OperationalError(dummy_sql_for_retry_test, {}, RuntimeError('db down'))
            return 'ok'

        assert run_idempotent_db_operation(flaky_operation) == 'ok'
        assert calls['count'] == 2


def test_run_idempotent_db_operation_does_not_hide_non_retryable_errors(app):
    with app.app_context():
        def failing_operation():
            raise RuntimeError('boom')

        with pytest.raises(RuntimeError):
            run_idempotent_db_operation(failing_operation)

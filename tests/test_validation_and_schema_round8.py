import io
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.datastructures import FileStorage, MultiDict

from database.db import db
from models.finance import Finance
from models.goal import Goal
from models.user import User
from services.catalogs import normalize_finance_category
from services.db_resilience import run_idempotent_db_operation
from services.import_service import ImportValidationError, import_finances_from_file
from services.validators import parse_finance_form, validate_finance_data

TEST_SQL_STATEMENT = 'SELECT 1'


def test_finance_and_goal_user_id_are_non_nullable():
    assert Finance.__table__.c.user_id.nullable is False
    assert Goal.__table__.c.user_id.nullable is False


def test_finance_insert_with_null_user_id_raises_error(app):
    with app.app_context():
        finance = Finance(
            description='Conta sem usuário',
            value=25.0,
            category='Utilidades',
            subcategory='Água',
            type='Despesa',
            status='Pago',
            due_date=date(2026, 3, 10),
            user_id=None,
        )
        db.session.add(finance)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_goal_insert_with_null_user_id_raises_error(app):
    with app.app_context():
        goal = Goal(
            name='Meta sem usuário',
            target_amount=1000.0,
            user_id=None,
        )
        db.session.add(goal)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


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
    try:
        with app.app_context():
            user = User(
                username='budgetinvalidcat',
                email='budgetinvalidcat@example.com',
                name='Budget Invalid Cat',
            )
            user.set_password('Pass1234')
            db.session.add(user)
            db.session.commit()

        client.post(
            '/login',
            data={'identifier': 'budgetinvalidcat', 'password': 'Pass1234'},
            follow_redirects=True,
        )
        response = client.post(
            '/budgets/add',
            data={'category': 'OutraCategoria', 'limit_amount': '100', 'period': 'Mensal'},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b'Categoria inv\xc3\xa1lida. Selecione uma categoria permitida.' in response.data
    finally:
        with app.app_context():
            user = User.query.filter_by(username='budgetinvalidcat').first()
            if user is not None:
                db.session.delete(user)
                db.session.commit()


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
        call_count = 0

        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError(TEST_SQL_STATEMENT, {}, RuntimeError('db down'))
            return 'ok'

        assert run_idempotent_db_operation(flaky_operation) == 'ok'
        assert call_count == 2


def test_run_idempotent_db_operation_raises_after_max_retries(app):
    with app.app_context():
        original_max_retries = app.config.get('DB_IDEMPOTENT_MAX_RETRIES')
        original_backoff = app.config.get('DB_IDEMPOTENT_RETRY_BACKOFF_SECONDS')
        try:
            app.config['DB_IDEMPOTENT_MAX_RETRIES'] = 2
            app.config['DB_IDEMPOTENT_RETRY_BACKOFF_SECONDS'] = 0.25
            call_count = 0

            def always_failing_operation():
                nonlocal call_count
                call_count += 1
                raise OperationalError(TEST_SQL_STATEMENT, {}, RuntimeError('db still down'))

            with pytest.raises(OperationalError):
                run_idempotent_db_operation(always_failing_operation)

            assert call_count == 3
        finally:
            app.config['DB_IDEMPOTENT_MAX_RETRIES'] = original_max_retries
            app.config['DB_IDEMPOTENT_RETRY_BACKOFF_SECONDS'] = original_backoff


def test_run_idempotent_db_operation_applies_backoff(app):
    with app.app_context():
        original_max_retries = app.config.get('DB_IDEMPOTENT_MAX_RETRIES')
        original_backoff = app.config.get('DB_IDEMPOTENT_RETRY_BACKOFF_SECONDS')
        try:
            app.config['DB_IDEMPOTENT_MAX_RETRIES'] = 2
            app.config['DB_IDEMPOTENT_RETRY_BACKOFF_SECONDS'] = 0.25
            call_count = 0

            def always_failing_operation():
                nonlocal call_count
                call_count += 1
                raise OperationalError(TEST_SQL_STATEMENT, {}, RuntimeError('db still down'))

            with patch('services.db_resilience.time.sleep') as sleep_mock:
                with pytest.raises(OperationalError):
                    run_idempotent_db_operation(always_failing_operation)

            base_backoff = app.config['DB_IDEMPOTENT_RETRY_BACKOFF_SECONDS']
            expected_backoffs = [
                base_backoff * attempt
                for attempt in range(1, len(sleep_mock.call_args_list) + 1)
            ]

            assert call_count == 3
            assert [call.args[0] for call in sleep_mock.call_args_list] == expected_backoffs
        finally:
            app.config['DB_IDEMPOTENT_MAX_RETRIES'] = original_max_retries
            app.config['DB_IDEMPOTENT_RETRY_BACKOFF_SECONDS'] = original_backoff


def test_run_idempotent_db_operation_does_not_hide_non_retryable_errors(app):
    with app.app_context():
        def failing_operation():
            raise RuntimeError('boom')

        with pytest.raises(RuntimeError):
            run_idempotent_db_operation(failing_operation)

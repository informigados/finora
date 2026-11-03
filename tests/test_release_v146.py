import io
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.datastructures import FileStorage

from database.db import db
from models.account import BankTransaction, FinancialAccount
from models.finance import Finance
from models.goal import Goal
from models.budget import Budget
from models.user import User
from services.account_service import (
    AccountValidationError, get_reconciliation_candidates, parse_decimal, reconcile_transaction,
)
from services.import_service import ImportValidationError, _parse_money, import_finances_from_file
from services.validators import parse_finance_form


@pytest.mark.parametrize('value', ['NaN', 'sNaN', 'Infinity', '-Infinity', '1e9999999', '1000000000000'])
def test_invalid_money_is_rejected_before_database_or_calculation(app, value):
    with app.test_request_context():
        with pytest.raises(AccountValidationError):
            parse_decimal(value)
        with pytest.raises(ImportValidationError):
            _parse_money(value)
        payload, errors = parse_finance_form({
            'description': 'Teste', 'value': value, 'category': 'Alimentação',
            'type': 'Despesa', 'status': 'Pago', 'due_date': '2026-11-03',
        })
        assert payload is None and errors


def test_import_preserves_international_amount_and_skips_nonfinite_row(app):
    with app.app_context():
        content = 'descricao;valor;categoria;data\nCompra;1,234.56;Alimentação;2026-11-03\nInválida;NaN;Alimentação;2026-11-03\n'
        result = import_finances_from_file(FileStorage(
            stream=io.BytesIO(content.encode()), filename='entries.csv'), user_id=1)
        assert result.imported_rows == 1 and result.skipped_rows == 1
        assert result.entries[0].value == 1234.56
        assert _parse_money('1.234,56') == Decimal('1234.56')


def test_nonfinite_goal_budget_and_account_requests_do_not_persist(auth_client, app):
    for value in ['NaN', 'Infinity', '-Infinity']:
        for route, data in [
            ('/goals/add', {'name': 'Inválida', 'target_amount': value}),
            ('/budgets/add', {'category': 'Alimentação', 'period': 'Mensal', 'limit_amount': value}),
            ('/accounts/add', {'name': 'Inválida', 'account_type': 'checking', 'initial_balance': value}),
        ]:
            assert auth_client.post(route, data=data, follow_redirects=True).status_code == 200
    with app.app_context():
        assert Goal.query.count() == Budget.query.count() == FinancialAccount.query.count() == 0


def test_reconciliation_excludes_wrong_account_pending_and_already_used_entries(auth_client, app):
    with app.test_request_context():
        owner = User.query.filter_by(username='testuser').one()
        accounts = [FinancialAccount(user_id=owner.id, name=name, account_type='checking') for name in ['A', 'B']]
        db.session.add_all(accounts)
        db.session.flush()
        entries = [Finance(
            user_id=owner.id, description=str(index), value=50, category='Alimentação',
            type='Despesa', status=status, due_date=date(2026, 11, 3), account_id=account_id,
        ) for index, (status, account_id) in enumerate([
            ('Pago', accounts[0].id), ('Pago', accounts[1].id), ('Pendente', accounts[0].id),
            ('Pago', None),
        ])]
        transactions = [BankTransaction(
            user_id=owner.id, account_id=accounts[0].id, fingerprint=str(index),
            description='Extrato', amount=-50, transaction_date=date(2026, 11, 3),
        ) for index in range(3)]
        db.session.add_all(entries + transactions)
        db.session.commit()
        first, second, third = transactions
        assert {f.id for f in get_reconciliation_candidates(owner.id, first)} == {entries[0].id, entries[3].id}
        for entry in entries[1:3]:
            with pytest.raises(AccountValidationError):
                reconcile_transaction(first, entry)
        reconcile_transaction(first, entries[0])
        db.session.flush()
        with pytest.raises(AccountValidationError):
            reconcile_transaction(second, entries[0])
        with pytest.raises(AccountValidationError):
            reconcile_transaction(first, entries[3])
        reconcile_transaction(third, entries[3])
        assert entries[3].account_id == accounts[0].id


def test_invalid_period_links_return_404_instead_of_rendering_failure(auth_client):
    for path in ['/dashboard/2026/13', '/dashboard/2026/0', '/dashboard/10000/1',
                 '/dashboard/10000', '/export/pdf/2026/13']:
        assert auth_client.get(path).status_code == 404


def test_editing_reconciled_amount_reopens_bank_transaction(auth_client, app):
    with app.app_context():
        owner = User.query.filter_by(username='testuser').one()
        account = FinancialAccount(user_id=owner.id, name='Banco', account_type='checking')
        db.session.add(account)
        db.session.flush()
        entry = Finance(user_id=owner.id, description='Compra', value=50, category='Alimentação',
                        type='Despesa', status='Pago', due_date=date(2026, 11, 3), account_id=account.id)
        db.session.add(entry)
        db.session.flush()
        transaction = BankTransaction(user_id=owner.id, account_id=account.id, fingerprint='edit',
                                      description='Extrato', amount=-50, transaction_date=date(2026, 11, 3),
                                      reconciled_finance_id=entry.id)
        db.session.add(transaction)
        db.session.commit()
        entry_id, account_id, transaction_id = entry.id, account.id, transaction.id
    result = auth_client.post(f'/entries/edit/{entry_id}', data={
        'description': 'Compra corrigida', 'value': '75', 'category': 'Alimentação',
        'type': 'Despesa', 'status': 'Pago', 'due_date': '2026-11-03', 'account_id': account_id,
    }, follow_redirects=True)
    assert result.status_code == 200
    with app.app_context():
        assert db.session.get(Finance, entry_id).value == 75
        assert db.session.get(BankTransaction, transaction_id).reconciled_finance_id is None


def test_pdf_supports_unicode_and_keeps_columns_inside_page(auth_client, app):
    from services.reports import DETAIL_COL_WIDTHS, PDFReport, generate_pdf_report
    from services.calculations import get_monthly_stats

    with app.test_request_context():
        owner = User.query.filter_by(username='testuser').one()
        entry = Finance(user_id=owner.id, description='Café – € e Łódź', value=1234.56,
                        category='Alimentação', type='Despesa', status='Pago', due_date=date(2026, 11, 3))
        db.session.add(entry)
        db.session.commit()
        pdf = PDFReport()
        assert sum(DETAIL_COL_WIDTHS) <= pdf.epw + 0.01
        result = generate_pdf_report(11, 2026, [entry] * 60, get_monthly_stats(11, 2026, owner.id))
        assert result.startswith(b'%PDF-')

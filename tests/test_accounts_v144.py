import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from werkzeug.datastructures import MultiDict

from database.db import db
from models.account import AccountTransfer, BankImportProfile, BankTransaction, FinancialAccount
from models.finance import Finance
from models.user import User
from services.account_service import (
    AccountValidationError,
    create_transfer,
    get_account_summaries,
    parse_decimal,
    validate_account_payload,
    validate_import_profile_payload,
)
from services.calculations import get_monthly_stats


def _user(app, username='testuser'):
    with app.app_context():
        return User.query.filter_by(username=username).first().id


def test_account_balances_include_paid_entries_and_neutral_transfers(auth_client, app):
    user_id = _user(app)
    with app.app_context():
        checking = FinancialAccount(
            user_id=user_id,
            name='Conta principal',
            account_type='checking',
            initial_balance=Decimal('1000.00'),
        )
        wallet = FinancialAccount(
            user_id=user_id,
            name='Carteira',
            account_type='wallet',
            initial_balance=Decimal('50.00'),
        )
        db.session.add_all((checking, wallet))
        db.session.flush()
        db.session.add_all(
            (
                Finance(
                    description='Salário',
                    value=500,
                    category='Trabalho',
                    type='Receita',
                    status='Pago',
                    due_date=date(2026, 7, 5),
                    user_id=user_id,
                    account_id=checking.id,
                ),
                Finance(
                    description='Mercado',
                    value=120,
                    category='Alimentação',
                    type='Despesa',
                    status='Pago',
                    due_date=date(2026, 7, 6),
                    user_id=user_id,
                    account_id=checking.id,
                ),
                AccountTransfer(
                    user_id=user_id,
                    source_account_id=checking.id,
                    destination_account_id=wallet.id,
                    amount=200,
                    transfer_date=date(2026, 7, 7),
                ),
            )
        )
        db.session.commit()

        summaries, consolidated = get_account_summaries(user_id)
        balances = {item['account'].name: item['balance'] for item in summaries}
        assert balances['Conta principal'] == Decimal('1180.00')
        assert balances['Carteira'] == Decimal('250.00')
        assert consolidated == Decimal('1430.00')


def test_monthly_stats_separate_realized_projected_receivable_and_payable(app):
    with app.app_context():
        user = User(username='metric144', email='metric144@example.com', name='Metric 144')
        user.set_password('Password123')
        db.session.add(user)
        db.session.flush()
        db.session.add_all(
            (
                Finance(description='Recebida', value=1000, category='Trabalho', type='Receita', status='Pago', due_date=date(2026, 7, 1), user_id=user.id),
                Finance(description='A receber', value=300, category='Trabalho', type='Receita', status='Pendente', due_date=date(2026, 7, 2), user_id=user.id),
                Finance(description='Paga', value=400, category='Moradia', type='Despesa', status='Pago', due_date=date(2026, 7, 3), user_id=user.id),
                Finance(description='A pagar', value=150, category='Moradia', type='Despesa', status='Atrasado', due_date=date(2026, 7, 4), user_id=user.id),
            )
        )
        db.session.commit()

        stats = get_monthly_stats(7, 2026, user.id)
        assert stats['receitas_recebidas'] == 1000
        assert stats['despesas_pagas'] == 400
        assert stats['a_receber'] == 300
        assert stats['a_pagar'] == 150
        assert stats['saldo_realizado'] == 600
        assert stats['saldo_projetado'] == 750
        assert stats['income_chart_labels'] == ['Trabalho']


def test_accounts_routes_transfer_import_ofx_and_reconcile(auth_client, app):
    auth_client.post(
        '/accounts/add',
        data={
            'name': 'Banco Azul',
            'account_type': 'checking',
            'institution': 'Banco Teste',
            'last_four': '4321',
            'color': '#2563EB',
            'initial_balance': '100.00',
        },
    )
    auth_client.post(
        '/accounts/add',
        data={
            'name': 'Carteira física',
            'account_type': 'wallet',
            'color': '#059669',
            'initial_balance': '20.00',
        },
    )
    with app.app_context():
        accounts = FinancialAccount.query.order_by(FinancialAccount.id).all()
        source_id, destination_id = accounts[0].id, accounts[1].id

    transfer_response = auth_client.post(
        '/accounts/transfers/add',
        data={
            'source_account_id': source_id,
            'destination_account_id': destination_id,
            'amount': '25.50',
            'transfer_date': '2026-07-20',
            'description': 'Dinheiro para a carteira',
        },
        follow_redirects=True,
    )
    assert transfer_response.status_code == 200
    assert 'sem afetar receitas ou despesas' in transfer_response.get_data(as_text=True)

    ofx = b'''OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260720120000<TRNAMT>250.00<FITID>credit-1<MEMO>Pagamento cliente</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260721120000<TRNAMT>-45.90<FITID>debit-1<MEMO>Compra mercado</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>'''
    import_response = auth_client.post(
        '/accounts/statements/import',
        data={'account_id': source_id, 'file': (io.BytesIO(ofx), 'extrato.ofx')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert import_response.status_code == 200
    assert '2 movimenta' in import_response.get_data(as_text=True)

    duplicate_response = auth_client.post(
        '/accounts/statements/import',
        data={'account_id': source_id, 'file': (io.BytesIO(ofx), 'extrato.ofx')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert '2 duplicata' in duplicate_response.get_data(as_text=True)

    with app.app_context():
        transaction = BankTransaction.query.filter(BankTransaction.amount > 0).one()
        transaction_id = transaction.id
    reconcile_response = auth_client.post(
        f'/accounts/reconciliation/{transaction_id}/create',
        follow_redirects=True,
    )
    assert 'criado e conciliado' in reconcile_response.get_data(as_text=True)
    with app.app_context():
        transaction = db.session.get(BankTransaction, transaction_id)
        assert transaction.reconciled_finance_id is not None
        assert transaction.reconciled_finance.account_id == source_id
        assert transaction.reconciled_finance.type == 'Receita'


def test_reusable_csv_profile_imports_statement(auth_client, app):
    auth_client.post(
        '/accounts/add',
        data={'name': 'Conta CSV', 'account_type': 'savings', 'color': '#7C3AED', 'initial_balance': '0'},
    )
    with app.app_context():
        account_id = FinancialAccount.query.filter_by(name='Conta CSV').one().id
    auth_client.post(
        '/accounts/import-profiles/add',
        data={
            'name': 'Extrato banco CSV',
            'file_type': 'csv',
            'delimiter': ';',
            'account_id': account_id,
            'date_column': 'Data',
            'description_column': 'Historico',
            'amount_column': 'Valor',
            'reference_column': 'Documento',
        },
    )
    with app.app_context():
        profile_id = BankImportProfile.query.one().id

    csv_payload = 'Data;Historico;Valor;Documento\n20/07/2026;Pix recebido;99,90;abc-1\n'.encode('utf-8')
    response = auth_client.post(
        '/accounts/statements/import',
        data={
            'account_id': account_id,
            'profile_id': profile_id,
            'file': (io.BytesIO(csv_payload), 'extrato.csv'),
        },
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        transaction = BankTransaction.query.one()
        assert transaction.amount == Decimal('99.90')
        assert transaction.source == 'csv'


def test_accounts_navigation_dashboard_flexibility_and_content_wrapping(auth_client):
    dashboard_html = auth_client.get('/dashboard/2026/7').get_data(as_text=True)
    assert 'Receitas recebidas' in dashboard_html
    assert 'Despesas pagas' in dashboard_html
    assert 'A receber' in dashboard_html
    assert 'A pagar' in dashboard_html
    assert 'incomeChart' in dashboard_html
    assert 'dashboardSidebarToggle' in dashboard_html
    assert 'data-lucide="landmark"' in dashboard_html

    accounts_response = auth_client.get('/accounts')
    assert accounts_response.status_code == 200
    assert 'Saldo consolidado' in accounts_response.get_data(as_text=True)

    css = Path('static/css/style.css').read_text(encoding='utf-8')
    assert 'overflow-wrap: anywhere' in css
    assert '.activity-detail-badge' in css


def test_account_management_profile_and_reconciliation_lifecycle(auth_client, app):
    for name in ('Operacional', 'Reserva'):
        response = auth_client.post(
            '/accounts/add',
            data={
                'name': name,
                'account_type': 'checking',
                'color': '#2563EB',
                'initial_balance': '10,00',
            },
            follow_redirects=True,
        )
        assert 'Conta adicionada com sucesso' in response.get_data(as_text=True)

    with app.app_context():
        operational = FinancialAccount.query.filter_by(name='Operacional').one()
        reserve = FinancialAccount.query.filter_by(name='Reserva').one()
        operational_id, reserve_id = operational.id, reserve.id

    response = auth_client.post(
        f'/accounts/{operational_id}/edit',
        data={
            'name': 'Operacional principal',
            'account_type': 'savings',
            'institution': 'Banco Azul',
            'last_four': '1234',
            'color': '#059669',
            'initial_balance': '20.00',
        },
        follow_redirects=True,
    )
    assert 'Conta atualizada com sucesso' in response.get_data(as_text=True)
    assert 'Conta arquivada' in auth_client.post(
        f'/accounts/{operational_id}/toggle', follow_redirects=True
    ).get_data(as_text=True)
    assert 'Conta reativada' in auth_client.post(
        f'/accounts/{operational_id}/toggle', follow_redirects=True
    ).get_data(as_text=True)
    assert auth_client.post('/accounts/999999/edit', data={}, follow_redirects=True).status_code == 200

    bad_transfer = auth_client.post(
        '/accounts/transfers/add',
        data={
            'source_account_id': operational_id,
            'destination_account_id': operational_id,
            'amount': '1',
            'transfer_date': '2026-07-20',
        },
        follow_redirects=True,
    )
    assert 'origem e destino diferentes' in bad_transfer.get_data(as_text=True)
    auth_client.post(
        '/accounts/transfers/add',
        data={
            'source_account_id': operational_id,
            'destination_account_id': reserve_id,
            'amount': '2',
            'transfer_date': '2026-07-20',
        },
    )
    with app.app_context():
        transfer_id = AccountTransfer.query.one().id
    assert 'Transferência excluída' in auth_client.post(
        f'/accounts/transfers/{transfer_id}/delete', follow_redirects=True
    ).get_data(as_text=True)

    invalid_profile = auth_client.post(
        '/accounts/import-profiles/add',
        data={'account_id': operational_id, 'name': 'Incompleto', 'file_type': 'csv'},
        follow_redirects=True,
    )
    assert 'Mapeie as colunas' in invalid_profile.get_data(as_text=True)
    profile_data = {
        'account_id': operational_id,
        'name': 'Banco padrão',
        'file_type': 'csv',
        'delimiter': ';',
        'date_column': 'Data',
        'description_column': 'Descrição',
        'amount_column': 'Valor',
    }
    auth_client.post('/accounts/import-profiles/add', data=profile_data)
    duplicate = auth_client.post('/accounts/import-profiles/add', data=profile_data, follow_redirects=True)
    assert 'Já existe um perfil' in duplicate.get_data(as_text=True)
    with app.app_context():
        profile_id = BankImportProfile.query.filter_by(name='Banco padrão').one().id
        user_id = _user(app)
        finance = Finance(
            description='Receita já lançada', value=75, category='Trabalho', type='Receita',
            status='Pago', due_date=date(2026, 7, 20), user_id=user_id,
        )
        transaction = BankTransaction(
            user_id=user_id, account_id=operational_id, fingerprint='manual-match',
            transaction_date=date(2026, 7, 20), description='Receita já lançada',
            amount=Decimal('75.00'), source='ofx',
        )
        db.session.add_all((finance, transaction))
        db.session.commit()
        finance_id, transaction_id = finance.id, transaction.id

    assert auth_client.get(f'/accounts?account={operational_id}&reconciliation=all').status_code == 200
    assert auth_client.get('/accounts?account=999999&reconciliation=unknown').status_code == 200
    matched = auth_client.post(
        f'/accounts/reconciliation/{transaction_id}/match',
        data={'finance_id': finance_id},
        follow_redirects=True,
    )
    assert 'conciliada com sucesso' in matched.get_data(as_text=True)
    assert auth_client.get('/accounts?reconciliation=reconciled').status_code == 200
    assert 'Conciliação desfeita' in auth_client.post(
        f'/accounts/reconciliation/{transaction_id}/undo', follow_redirects=True
    ).get_data(as_text=True)
    assert auth_client.post('/accounts/reconciliation/999999/match', data={'finance_id': 0}).status_code == 302
    assert auth_client.post('/accounts/reconciliation/999999/create').status_code == 302
    assert auth_client.post('/accounts/reconciliation/999999/undo').status_code == 302
    assert 'Perfil de importação excluído' in auth_client.post(
        f'/accounts/import-profiles/{profile_id}/delete', follow_redirects=True
    ).get_data(as_text=True)


def test_accounts_reject_invalid_inputs_and_statement_formats(auth_client, app):
    bad_account = auth_client.post(
        '/accounts/add',
        data={'name': '', 'account_type': 'invalid', 'color': 'red', 'initial_balance': 'abc'},
        follow_redirects=True,
    )
    assert 'valor válido' in bad_account.get_data(as_text=True)
    assert 'Selecione a conta e o arquivo' in auth_client.post(
        '/accounts/statements/import', data={}, follow_redirects=True
    ).get_data(as_text=True)

    auth_client.post(
        '/accounts/add',
        data={'name': 'Importação', 'account_type': 'checking', 'color': '#2563EB', 'initial_balance': '0'},
    )
    with app.app_context():
        account_id = FinancialAccount.query.filter_by(name='Importação').one().id
    invalid_file = auth_client.post(
        '/accounts/statements/import',
        data={'account_id': account_id, 'file': (io.BytesIO(b'teste'), 'extrato.txt')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert 'Formato inválido' in invalid_file.get_data(as_text=True)


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        (12, Decimal('12.00')),
        ('R$ 1.234,56', Decimal('1234.56')),
        ('1,234.56', Decimal('1234.56')),
        ('(25,50)', Decimal('-25.50')),
    ],
)
def test_account_decimal_parser_handles_financial_formats(raw, expected):
    assert parse_decimal(raw) == expected


@pytest.mark.parametrize(
    'override',
    [
        {'name': ''},
        {'account_type': 'invalid'},
        {'institution': 'x' * 101},
        {'last_four': '12'},
        {'color': '#FFFFFF'},
    ],
)
def test_account_payload_rejects_each_invalid_field(override):
    payload = {
        'name': 'Conta válida',
        'account_type': 'checking',
        'institution': '',
        'last_four': '',
        'color': '#2563EB',
        'initial_balance': '0',
    }
    payload.update(override)
    with pytest.raises(AccountValidationError):
        validate_account_payload(payload)


def test_account_decimal_parser_rejects_empty_values():
    with pytest.raises(AccountValidationError):
        parse_decimal(None)


def test_transfer_and_import_profile_validation_edges(app):
    with app.test_request_context('/'):
        user = User(username='validation144', email='validation144@example.com', name='Validation')
        user.set_password('Password123')
        db.session.add(user)
        db.session.flush()
        user_id = user.id
        first = FinancialAccount(user_id=user_id, name='Primeira', account_type='checking')
        second = FinancialAccount(user_id=user_id, name='Segunda', account_type='checking')
        db.session.add_all((first, second))
        db.session.commit()

        base = MultiDict({
            'source_account_id': str(first.id),
            'destination_account_id': str(second.id),
            'amount': '10',
            'transfer_date': '2026-07-20',
        })
        unavailable = base.copy()
        unavailable['destination_account_id'] = '999999'
        with pytest.raises(AccountValidationError):
            create_transfer(user_id, unavailable)
        non_positive = base.copy()
        non_positive['amount'] = '0'
        with pytest.raises(AccountValidationError):
            create_transfer(user_id, non_positive)
        invalid_date = base.copy()
        invalid_date['transfer_date'] = '20/07/2026'
        with pytest.raises(AccountValidationError):
            create_transfer(user_id, invalid_date)

        with pytest.raises(AccountValidationError):
            validate_import_profile_payload({'name': '', 'file_type': 'csv'})
        with pytest.raises(AccountValidationError):
            validate_import_profile_payload({'name': 'Perfil', 'file_type': 'txt'})

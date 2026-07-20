from datetime import date

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required
from flask.typing import ResponseReturnValue
from sqlalchemy.exc import IntegrityError

from database.db import db
from models.account import AccountTransfer, BankImportProfile, BankTransaction, FinancialAccount
from models.finance import Finance
from services.account_service import (
    AccountValidationError,
    create_finance_from_transaction,
    create_transfer,
    get_account_summaries,
    get_account_color_options,
    get_account_type_options,
    get_reconciliation_candidates,
    import_bank_statement,
    reconcile_transaction,
    validate_account_payload,
    validate_import_profile_payload,
)
from services.ownership import get_owned_or_none
from services.profile_service import record_activity, record_system_event


accounts_bp = Blueprint('accounts', __name__)
ACCOUNTS_HISTORY_PER_PAGE = 12
RECONCILIATION_PER_PAGE = 20


def _accounts_redirect(anchor: str = '', **params) -> ResponseReturnValue:
    target = url_for('accounts.index', **{key: value for key, value in params.items() if value})
    if anchor:
        target = f'{target}#{anchor}'
    return redirect(target)


@accounts_bp.route('/accounts')
@login_required
def index() -> ResponseReturnValue:
    summaries, consolidated_balance = get_account_summaries(current_user.id)
    active_accounts = [item['account'] for item in summaries if item['account'].is_active]

    transfers_page = max(request.args.get('transfers_page', 1, type=int) or 1, 1)
    transfers_pagination = AccountTransfer.query.filter_by(user_id=current_user.id).order_by(
        AccountTransfer.transfer_date.desc(),
        AccountTransfer.id.desc(),
    ).paginate(page=transfers_page, per_page=ACCOUNTS_HISTORY_PER_PAGE, error_out=False)

    selected_account_id = request.args.get('account', type=int)
    transactions_query = BankTransaction.query.filter_by(user_id=current_user.id)
    if selected_account_id:
        selected_account = get_owned_or_none(FinancialAccount, selected_account_id, current_user.id)
        if selected_account:
            transactions_query = transactions_query.filter_by(account_id=selected_account.id)
        else:
            selected_account_id = None
    reconciliation_filter = request.args.get('reconciliation', 'pending')
    if reconciliation_filter == 'reconciled':
        transactions_query = transactions_query.filter(BankTransaction.reconciled_finance_id.isnot(None))
    elif reconciliation_filter == 'all':
        reconciliation_filter = 'all'
    else:
        reconciliation_filter = 'pending'
        transactions_query = transactions_query.filter(BankTransaction.reconciled_finance_id.is_(None))

    reconciliation_page = max(request.args.get('reconciliation_page', 1, type=int) or 1, 1)
    transactions_pagination = transactions_query.order_by(
        BankTransaction.transaction_date.desc(),
        BankTransaction.id.desc(),
    ).paginate(page=reconciliation_page, per_page=RECONCILIATION_PER_PAGE, error_out=False)
    candidates = {
        transaction.id: get_reconciliation_candidates(current_user.id, transaction)
        for transaction in transactions_pagination.items
        if transaction.reconciled_finance_id is None
    }

    import_profiles = BankImportProfile.query.filter_by(user_id=current_user.id).order_by(
        BankImportProfile.name.asc()
    ).all()
    pending_reconciliation_count = BankTransaction.query.filter_by(
        user_id=current_user.id,
        reconciled_finance_id=None,
    ).count()

    return render_template(
        'accounts.html',
        account_summaries=summaries,
        active_accounts=active_accounts,
        consolidated_balance=consolidated_balance,
        transfers_pagination=transfers_pagination,
        transactions_pagination=transactions_pagination,
        candidates=candidates,
        import_profiles=import_profiles,
        account_type_labels=dict(get_account_type_options()),
        account_color_options=get_account_color_options(),
        selected_account_id=selected_account_id,
        reconciliation_filter=reconciliation_filter,
        pending_reconciliation_count=pending_reconciliation_count,
        today=date.today(),
    )


@accounts_bp.route('/accounts/add', methods=['POST'])
@login_required
def add_account() -> ResponseReturnValue:
    try:
        payload = validate_account_payload(request.form)
        account = FinancialAccount(user_id=current_user.id, **payload)
        db.session.add(account)
        record_activity(
            current_user,
            'accounts',
            'financial_account_created',
            'Conta financeira criada com sucesso.',
            details={'name': account.name, 'account_type': account.account_type},
            ip_address=request.remote_addr,
            commit=False,
        )
        db.session.commit()
        flash(_('Conta adicionada com sucesso.'), 'success')
    except AccountValidationError as exc:
        db.session.rollback()
        flash(_(str(exc)), 'error')
    except IntegrityError:
        db.session.rollback()
        flash(_('Já existe uma conta com esse nome.'), 'error')
    return _accounts_redirect('accounts-overview')


@accounts_bp.route('/accounts/<int:account_id>/edit', methods=['POST'])
@login_required
def edit_account(account_id: int) -> ResponseReturnValue:
    account = get_owned_or_none(FinancialAccount, account_id, current_user.id)
    if not account:
        flash(_('Conta não encontrada.'), 'error')
        return _accounts_redirect('accounts-overview')
    try:
        payload = validate_account_payload(request.form)
        for key, value in payload.items():
            setattr(account, key, value)
        record_activity(
            current_user,
            'accounts',
            'financial_account_updated',
            'Conta financeira atualizada com sucesso.',
            details={'account_id': account.id, 'name': account.name},
            ip_address=request.remote_addr,
            commit=False,
        )
        db.session.commit()
        flash(_('Conta atualizada com sucesso.'), 'success')
    except AccountValidationError as exc:
        db.session.rollback()
        flash(_(str(exc)), 'error')
    except IntegrityError:
        db.session.rollback()
        flash(_('Já existe uma conta com esse nome.'), 'error')
    return _accounts_redirect('accounts-overview')


@accounts_bp.route('/accounts/<int:account_id>/toggle', methods=['POST'])
@login_required
def toggle_account(account_id: int) -> ResponseReturnValue:
    account = get_owned_or_none(FinancialAccount, account_id, current_user.id)
    if account:
        account.is_active = not account.is_active
        db.session.commit()
        flash(
            _('Conta reativada.') if account.is_active else _('Conta arquivada sem apagar o histórico.'),
            'success',
        )
    return _accounts_redirect('accounts-overview')


@accounts_bp.route('/accounts/transfers/add', methods=['POST'])
@login_required
def add_transfer() -> ResponseReturnValue:
    try:
        transfer = create_transfer(current_user.id, request.form)
        db.session.add(transfer)
        record_activity(
            current_user,
            'accounts',
            'transfer_created',
            'Transferência entre contas registrada.',
            details={
                'source_account_id': transfer.source_account_id,
                'destination_account_id': transfer.destination_account_id,
                'amount': float(transfer.amount),
            },
            ip_address=request.remote_addr,
            commit=False,
        )
        db.session.commit()
        flash(_('Transferência registrada sem afetar receitas ou despesas.'), 'success')
    except AccountValidationError as exc:
        db.session.rollback()
        flash(_(str(exc)), 'error')
    return _accounts_redirect('transfers')


@accounts_bp.route('/accounts/transfers/<int:transfer_id>/delete', methods=['POST'])
@login_required
def delete_transfer(transfer_id: int) -> ResponseReturnValue:
    transfer = get_owned_or_none(AccountTransfer, transfer_id, current_user.id)
    if transfer:
        db.session.delete(transfer)
        db.session.commit()
        flash(_('Transferência excluída.'), 'success')
    return _accounts_redirect('transfers')


@accounts_bp.route('/accounts/import-profiles/add', methods=['POST'])
@login_required
def add_import_profile() -> ResponseReturnValue:
    account_id = request.form.get('account_id', type=int)
    if account_id and not get_owned_or_none(FinancialAccount, account_id, current_user.id):
        flash(_('Conta não encontrada.'), 'error')
        return _accounts_redirect('statement-import')
    try:
        payload = validate_import_profile_payload(request.form)
        profile = BankImportProfile(user_id=current_user.id, account_id=account_id, **payload)
        db.session.add(profile)
        db.session.commit()
        flash(_('Perfil de importação salvo.'), 'success')
    except AccountValidationError as exc:
        db.session.rollback()
        flash(_(str(exc)), 'error')
    except IntegrityError:
        db.session.rollback()
        flash(_('Já existe um perfil com esse nome.'), 'error')
    return _accounts_redirect('statement-import')


@accounts_bp.route('/accounts/import-profiles/<int:profile_id>/delete', methods=['POST'])
@login_required
def delete_import_profile(profile_id: int) -> ResponseReturnValue:
    profile = get_owned_or_none(BankImportProfile, profile_id, current_user.id)
    if profile:
        db.session.delete(profile)
        db.session.commit()
        flash(_('Perfil de importação excluído.'), 'success')
    return _accounts_redirect('statement-import')


@accounts_bp.route('/accounts/statements/import', methods=['POST'])
@login_required
def import_statement() -> ResponseReturnValue:
    account = get_owned_or_none(
        FinancialAccount,
        request.form.get('account_id', type=int),
        current_user.id,
    )
    uploaded_file = request.files.get('file')
    if not account or not uploaded_file:
        flash(_('Selecione a conta e o arquivo do extrato.'), 'error')
        return _accounts_redirect('statement-import')

    profile = None
    profile_id = request.form.get('profile_id', type=int)
    if profile_id:
        profile = get_owned_or_none(BankImportProfile, profile_id, current_user.id)
    try:
        result = import_bank_statement(
            uploaded_file,
            account,
            profile,
            max_rows=current_app.config.get('MAX_IMPORT_ROWS', 20000),
            max_file_size=current_app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024),
        )
        db.session.add_all(result.transactions)
        record_activity(
            current_user,
            'accounts',
            'statement_imported',
            'Extrato bancário importado.',
            details={
                'account_id': account.id,
                'imported_rows': result.imported_rows,
                'duplicate_rows': result.duplicate_rows,
                'filename': uploaded_file.filename,
            },
            ip_address=request.remote_addr,
            commit=False,
        )
        db.session.commit()
        flash(
            _(
                '%(count)d movimentação(ões) importada(s); %(duplicates)d duplicata(s) ignorada(s).',
                count=result.imported_rows,
                duplicates=result.duplicate_rows,
            ),
            'success',
        )
    except AccountValidationError as exc:
        db.session.rollback()
        flash(_(str(exc)), 'error')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Falha inesperada ao importar extrato bancário.')
        record_system_event(
            'error',
            'accounts',
            'Falha inesperada ao importar extrato bancário.',
            user=current_user,
            event_code='statement_import_failed',
            details={'filename': uploaded_file.filename or ''},
        )
        flash(_('Não foi possível importar o extrato.'), 'error')
    return _accounts_redirect('reconciliation', account=account.id)


@accounts_bp.route('/accounts/reconciliation/<int:transaction_id>/match', methods=['POST'])
@login_required
def match_transaction(transaction_id: int) -> ResponseReturnValue:
    transaction = get_owned_or_none(BankTransaction, transaction_id, current_user.id)
    finance = get_owned_or_none(Finance, request.form.get('finance_id', type=int), current_user.id)
    if not transaction or not finance:
        flash(_('Movimentação ou lançamento não encontrado.'), 'error')
        return _accounts_redirect('reconciliation')
    try:
        reconcile_transaction(transaction, finance)
        db.session.commit()
        flash(_('Movimentação conciliada com sucesso.'), 'success')
    except AccountValidationError as exc:
        db.session.rollback()
        flash(_(str(exc)), 'error')
    return _accounts_redirect('reconciliation', account=transaction.account_id)


@accounts_bp.route('/accounts/reconciliation/<int:transaction_id>/create', methods=['POST'])
@login_required
def create_reconciled_entry(transaction_id: int) -> ResponseReturnValue:
    transaction = get_owned_or_none(BankTransaction, transaction_id, current_user.id)
    if transaction and transaction.reconciled_finance_id is None:
        create_finance_from_transaction(transaction)
        db.session.commit()
        flash(_('Lançamento criado e conciliado com sucesso.'), 'success')
        return _accounts_redirect('reconciliation', account=transaction.account_id)
    flash(_('A movimentação já foi conciliada ou não existe.'), 'error')
    return _accounts_redirect('reconciliation')


@accounts_bp.route('/accounts/reconciliation/<int:transaction_id>/undo', methods=['POST'])
@login_required
def undo_reconciliation(transaction_id: int) -> ResponseReturnValue:
    transaction = get_owned_or_none(BankTransaction, transaction_id, current_user.id)
    if transaction:
        transaction.reconciled_finance_id = None
        transaction.reconciled_at = None
        db.session.commit()
        flash(_('Conciliação desfeita. O lançamento foi preservado.'), 'success')
        return _accounts_redirect('reconciliation', account=transaction.account_id, reconciliation='reconciled')
    return _accounts_redirect('reconciliation')

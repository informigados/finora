from database.db import db
from models.time_utils import utcnow_naive


class FinancialAccount(db.Model):
    __tablename__ = 'financial_accounts'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_financial_account_user_name'),
        db.Index('ix_financial_accounts_user_active', 'user_id', 'is_active'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    account_type = db.Column(db.String(24), nullable=False, default='checking')
    institution = db.Column(db.String(100))
    last_four = db.Column(db.String(4))
    color = db.Column(db.String(7), nullable=False, default='#2563EB')
    initial_balance = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow_naive,
        onupdate=utcnow_naive,
    )

    finances = db.relationship('Finance', back_populates='account', lazy='dynamic')
    recurring_entries = db.relationship('RecurringEntry', back_populates='account', lazy='dynamic')
    bank_transactions = db.relationship(
        'BankTransaction',
        back_populates='account',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )
    import_profiles = db.relationship(
        'BankImportProfile',
        back_populates='account',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )


class AccountTransfer(db.Model):
    __tablename__ = 'account_transfers'
    __table_args__ = (
        db.CheckConstraint('source_account_id <> destination_account_id', name='ck_transfer_distinct_accounts'),
        db.CheckConstraint('amount > 0', name='ck_transfer_positive_amount'),
        db.Index('ix_account_transfers_user_date', 'user_id', 'transfer_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source_account_id = db.Column(
        db.Integer,
        db.ForeignKey('financial_accounts.id'),
        nullable=False,
    )
    destination_account_id = db.Column(
        db.Integer,
        db.ForeignKey('financial_accounts.id'),
        nullable=False,
    )
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    transfer_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(140))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)

    source_account = db.relationship(
        'FinancialAccount',
        foreign_keys=[source_account_id],
        backref=db.backref('outgoing_transfers', lazy='dynamic'),
    )
    destination_account = db.relationship(
        'FinancialAccount',
        foreign_keys=[destination_account_id],
        backref=db.backref('incoming_transfers', lazy='dynamic'),
    )


class BankImportProfile(db.Model):
    __tablename__ = 'bank_import_profiles'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_bank_import_profile_user_name'),
        db.Index('ix_bank_import_profiles_user_account', 'user_id', 'account_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('financial_accounts.id'), nullable=True)
    name = db.Column(db.String(80), nullable=False)
    file_type = db.Column(db.String(8), nullable=False)
    delimiter = db.Column(db.String(4), nullable=True)
    mapping_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow_naive,
        onupdate=utcnow_naive,
    )

    account = db.relationship('FinancialAccount', back_populates='import_profiles')


class BankTransaction(db.Model):
    __tablename__ = 'bank_transactions'
    __table_args__ = (
        db.UniqueConstraint('account_id', 'fingerprint', name='uq_bank_transaction_account_fingerprint'),
        db.Index('ix_bank_transactions_user_date', 'user_id', 'transaction_date'),
        db.Index('ix_bank_transactions_account_reconciled', 'account_id', 'reconciled_finance_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('financial_accounts.id'), nullable=False)
    external_id = db.Column(db.String(140))
    fingerprint = db.Column(db.String(64), nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    source = db.Column(db.String(16), nullable=False, default='ofx')
    reconciled_finance_id = db.Column(
        db.Integer,
        db.ForeignKey('finances.id', ondelete='SET NULL'),
        nullable=True,
    )
    reconciled_at = db.Column(db.DateTime)
    imported_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)

    account = db.relationship('FinancialAccount', back_populates='bank_transactions')
    reconciled_finance = db.relationship(
        'Finance',
        foreign_keys=[reconciled_finance_id],
        backref=db.backref('bank_reconciliations', lazy='dynamic'),
    )

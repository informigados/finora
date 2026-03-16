from sqlalchemy import inspect

from database.db import db


EXPECTED_FOUNDATION_TABLES = {
    'backup_schedules',
    'backup_records',
    'user_sessions',
    'activity_logs',
    'system_events',
    'app_update_state',
}


def test_phase1_foundation_tables_are_registered(app):
    with app.app_context():
        db.create_all()
        table_names = set(inspect(db.engine).get_table_names())

    assert EXPECTED_FOUNDATION_TABLES.issubset(table_names)


def test_phase1_foundation_columns_exist(app):
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)

        finance_columns = {column['name'] for column in inspector.get_columns('finances')}
        recurring_columns = {column['name'] for column in inspector.get_columns('recurring_entries')}
        user_columns = {column['name'] for column in inspector.get_columns('user')}

    assert {'subcategory', 'payment_method'}.issubset(finance_columns)
    assert {'subcategory', 'payment_method'}.issubset(recurring_columns)
    assert {
        'recovery_key_salt',
        'recovery_key_version',
        'password_reset_version',
        'recovery_key_generated_at',
        'recovery_key_last_sent_at',
        'last_login_at',
    }.issubset(user_columns)

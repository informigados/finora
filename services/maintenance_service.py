import threading

from sqlalchemy import inspect

from database.db import db
from services.recurring_service import process_all_recurring_entries

RECURRING_REQUIRED_TABLES = frozenset({'finances', 'recurring_entries'})


def recurring_schema_is_ready() -> bool:
    table_names = set(inspect(db.engine).get_table_names())
    return RECURRING_REQUIRED_TABLES.issubset(table_names)


def run_recurring_maintenance(app):
    with app.app_context():
        try:
            if not recurring_schema_is_ready():
                app.logger.warning(
                    'Rotina de recorrencias ignorada: schema incompleto. '
                    'Execute "flask db upgrade" antes de iniciar a manutencao.'
                )
                return {'processed_entries': 0, 'affected_users': 0, 'skipped': True}
        except Exception:
            app.logger.exception(
                'Falha ao validar o schema antes da rotina de recorrencias.'
            )
            return {'processed_entries': 0, 'affected_users': 0, 'skipped': True}

        result = process_all_recurring_entries()
        if result['processed_entries'] > 0:
            app.logger.info(
                'Rotina de recorrencias executada: %s lancamentos gerados para %s usuario(s).',
                result['processed_entries'],
                result['affected_users'],
            )
        return result


def start_recurring_scheduler(app):
    if app.config.get('TESTING') or not app.config.get('ENABLE_RECURRING_SCHEDULER', True):
        return None

    with app.app_context():
        try:
            if not recurring_schema_is_ready():
                app.logger.warning(
                    'Scheduler de recorrencias nao iniciado: schema incompleto. '
                    'Execute "flask db upgrade" e reinicie a aplicacao.'
                )
                return None
        except Exception:
            app.logger.exception(
                'Falha ao validar o schema antes de iniciar o scheduler de recorrencias.'
            )
            return None

        interval_seconds = max(
            int(app.config.get('RECURRING_PROCESS_INTERVAL_SECONDS', 300) or 300),
            60,
        )

    stop_event = threading.Event()

    def worker():
        while True:
            if stop_event.wait(interval_seconds):
                return
            try:
                run_recurring_maintenance(app)
            except Exception:
                app.logger.exception('Falha na rotina agendada de recorrencias.')

    thread = threading.Thread(
        target=worker,
        name='finora-recurring-scheduler',
        daemon=True,
    )
    thread.start()
    return stop_event

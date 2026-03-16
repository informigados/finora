import hashlib
import os
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from calendar import monthrange
from datetime import datetime, timedelta

from sqlalchemy import inspect

from database.db import db
from models.backup import BackupRecord, BackupSchedule
from models.time_utils import utcnow_naive
from models.user import User
from services.profile_service import record_activity, record_system_event


BACKUP_REQUIRED_TABLES = frozenset({'user', 'backup_schedules', 'backup_records'})
BACKUP_FREQUENCY_OPTIONS = ('Diário', 'Semanal', 'Mensal')
BACKUP_TIMES_PER_PERIOD_OPTIONS = tuple(range(1, 8))
BACKUP_WEEKDAY_OPTIONS = (
    (0, 'Segunda-feira'),
    (1, 'Terça-feira'),
    (2, 'Quarta-feira'),
    (3, 'Quinta-feira'),
    (4, 'Sexta-feira'),
    (5, 'Sábado'),
    (6, 'Domingo'),
)


def backup_schema_is_ready() -> bool:
    table_names = set(inspect(db.engine).get_table_names())
    return BACKUP_REQUIRED_TABLES.issubset(table_names)


def get_backup_weekday_label(day_of_week):
    for weekday_value, label in BACKUP_WEEKDAY_OPTIONS:
        if weekday_value == day_of_week:
            return label
    return None


def get_or_create_backup_schedule(user, default_retention_count):
    schedule = user.backup_schedule
    if schedule is not None:
        return schedule

    schedule = BackupSchedule(
        user_id=user.id,
        enabled=False,
        frequency='Semanal',
        times_per_period=1,
        day_of_week=0,
        day_of_month=1,
        run_hour=3,
        run_minute=0,
        retention_count=default_retention_count,
    )
    db.session.add(schedule)
    db.session.commit()
    return schedule


def _resolve_sqlite_backup_database_path(app):
    engine_url = db.engine.url
    if not engine_url.drivername.startswith('sqlite'):
        return None, 'Backup por arquivo está disponível apenas para SQLite. Use backup nativo do seu banco atual.'

    db_path = engine_url.database or ''
    if not db_path or db_path == ':memory:':
        return None, 'Banco de dados SQLite inválido para backup.'

    if not os.path.isabs(db_path):
        instance_candidate = os.path.join(app.instance_path, db_path)
        root_candidate = os.path.join(app.root_path, db_path)
        db_path = instance_candidate if os.path.exists(instance_candidate) else root_candidate

    if not os.path.exists(db_path):
        return None, 'Banco de dados não encontrado para backup.'

    return db_path, None


def _period_anchor_for_daily(reference_dt, run_hour, run_minute):
    anchor = reference_dt.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)
    if anchor > reference_dt:
        anchor -= timedelta(days=1)
    return anchor


def _period_anchor_for_weekly(reference_dt, day_of_week, run_hour, run_minute):
    week_start = reference_dt - timedelta(days=reference_dt.weekday())
    anchor = week_start.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)
    anchor += timedelta(days=day_of_week)
    if anchor > reference_dt:
        anchor -= timedelta(days=7)
    return anchor


def _shift_month(year, month, delta_months):
    shifted_month = month + delta_months
    shifted_year = year + (shifted_month - 1) // 12
    shifted_month = (shifted_month - 1) % 12 + 1
    return shifted_year, shifted_month


def _build_month_anchor(year, month, day_of_month, run_hour, run_minute):
    valid_day = min(max(int(day_of_month or 1), 1), monthrange(year, month)[1])
    return datetime(year, month, valid_day, run_hour, run_minute)


def _period_anchor_for_monthly(reference_dt, day_of_month, run_hour, run_minute):
    anchor = _build_month_anchor(
        reference_dt.year,
        reference_dt.month,
        day_of_month,
        run_hour,
        run_minute,
    )
    if anchor > reference_dt:
        prev_year, prev_month = _shift_month(reference_dt.year, reference_dt.month, -1)
        anchor = _build_month_anchor(prev_year, prev_month, day_of_month, run_hour, run_minute)
    return anchor


def _next_period_anchor(anchor, frequency, schedule):
    if frequency == 'Diário':
        return anchor + timedelta(days=1)
    if frequency == 'Semanal':
        return anchor + timedelta(days=7)
    if frequency == 'Mensal':
        next_year, next_month = _shift_month(anchor.year, anchor.month, 1)
        return _build_month_anchor(
            next_year,
            next_month,
            schedule.day_of_month,
            schedule.run_hour,
            schedule.run_minute,
        )
    return anchor + timedelta(days=1)


def _resolve_period_anchor(reference_dt, schedule):
    if schedule.frequency == 'Diário':
        return _period_anchor_for_daily(reference_dt, schedule.run_hour, schedule.run_minute)
    if schedule.frequency == 'Semanal':
        return _period_anchor_for_weekly(
            reference_dt,
            int(schedule.day_of_week or 0),
            schedule.run_hour,
            schedule.run_minute,
        )
    return _period_anchor_for_monthly(
        reference_dt,
        int(schedule.day_of_month or 1),
        schedule.run_hour,
        schedule.run_minute,
    )


def calculate_next_backup_run(schedule, from_dt=None):
    if not schedule.enabled:
        return None

    reference_dt = from_dt or utcnow_naive()
    anchor = _resolve_period_anchor(reference_dt, schedule)
    next_anchor = _next_period_anchor(anchor, schedule.frequency, schedule)
    times_per_period = max(int(schedule.times_per_period or 1), 1)
    interval = (next_anchor - anchor) / times_per_period

    for slot_index in range(times_per_period):
        candidate = anchor + (interval * slot_index)
        if candidate > reference_dt:
            return candidate

    return next_anchor


def _build_backup_archive(app, user_id):
    db_path, error_message = _resolve_sqlite_backup_database_path(app)
    if error_message:
        raise ValueError(error_message)

    timestamp = utcnow_naive().strftime("%Y%m%d_%H%M%S")
    filename = f"finora_backup_{timestamp}_{uuid.uuid4().hex[:8]}.zip"
    user_storage_dir = os.path.join(
        app.config.get('BACKUP_STORAGE_DIR', os.path.join(app.root_path, 'backups')),
        f'user_{user_id}',
    )
    os.makedirs(user_storage_dir, exist_ok=True)
    output_path = os.path.join(user_storage_dir, filename)

    with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as snapshot_file:
        snapshot_path = snapshot_file.name

    try:
        source = sqlite3.connect(db_path)
        destination = sqlite3.connect(snapshot_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
            backup_zip.write(snapshot_path, os.path.basename(db_path))
    finally:
        if os.path.exists(snapshot_path):
            os.remove(snapshot_path)

    checksum = _calculate_file_checksum(output_path)

    return {
        'filename': filename,
        'storage_path': output_path,
        'file_size_bytes': os.path.getsize(output_path),
        'checksum': checksum,
    }


def _calculate_file_checksum(file_path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with open(file_path, 'rb') as backup_file:
        while True:
            chunk = backup_file.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _cleanup_storage_file(path):
    if path and os.path.exists(path):
        os.remove(path)


def enforce_backup_retention(user_id, retention_count, skip_record_id=None):
    retained_records = (
        BackupRecord.query.filter_by(user_id=user_id, status='Concluido')
        .order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc())
        .all()
    )
    for stale_record in retained_records[max(int(retention_count or 1), 1):]:
        if skip_record_id and stale_record.id == skip_record_id:
            continue
        _cleanup_storage_file(stale_record.storage_path)
        db.session.delete(stale_record)


def create_backup_for_user(user, app, trigger_source='Manual', schedule=None):
    created_files = []
    try:
        metadata = _build_backup_archive(app, user.id)
        created_files.append(metadata['storage_path'])

        backup_record = BackupRecord(
            user_id=user.id,
            schedule_id=getattr(schedule, 'id', None),
            trigger_source=trigger_source,
            status='Concluido',
            file_name=metadata['filename'],
            storage_path=metadata['storage_path'],
            file_size_bytes=metadata['file_size_bytes'],
            checksum=metadata['checksum'],
        )
        db.session.add(backup_record)
        record_activity(
            user,
            'backup',
            'backup_generated',
            'Backup gerado com sucesso.',
            details={
                'file_name': metadata['filename'],
                'trigger_source': trigger_source,
            },
            commit=False,
        )

        if schedule is not None:
            run_reference = utcnow_naive()
            schedule.last_run_at = run_reference
            schedule.next_run_at = calculate_next_backup_run(schedule, from_dt=run_reference)

        retention_count = (
            int(getattr(schedule, 'retention_count', 0) or 0)
            or int(getattr(user.backup_schedule, 'retention_count', 0) or 0)
            or int(app.config.get('BACKUP_DEFAULT_RETENTION_COUNT', 20))
        )
        db.session.flush()
        enforce_backup_retention(user.id, retention_count, skip_record_id=backup_record.id)
        db.session.commit()
        return backup_record
    except Exception as exc:
        db.session.rollback()
        for created_file in created_files:
            _cleanup_storage_file(created_file)
        record_system_event(
            'error',
            'backup',
            'Falha ao gerar backup.',
            user=user,
            event_code='backup_generation_failed',
            details={'error': str(exc), 'trigger_source': trigger_source},
        )
        raise


def delete_backup_record(user, backup_record):
    try:
        _cleanup_storage_file(backup_record.storage_path)
        record_activity(
            user,
            'backup',
            'backup_deleted',
            'Backup removido com sucesso.',
            details={'file_name': backup_record.file_name},
            commit=False,
        )
        db.session.delete(backup_record)
        db.session.commit()
        return None
    except Exception:
        db.session.rollback()
        record_system_event(
            'error',
            'backup',
            'Falha ao remover backup salvo.',
            user=user,
            event_code='backup_delete_failed',
            details={'file_name': backup_record.file_name},
        )
        return 'backup_delete_failed'


def apply_backup_schedule_update(user, form, default_retention_count):
    enabled = bool(form.get('enabled'))
    frequency = (form.get('frequency') or 'Semanal').strip()
    try:
        times_per_period = int(form.get('times_per_period') or 1)
        run_hour = int(form.get('run_hour') or 3)
        run_minute = int(form.get('run_minute') or 0)
        retention_count = int(form.get('retention_count') or default_retention_count)
        day_of_week = int(form.get('day_of_week') or 0)
        day_of_month = int(form.get('day_of_month') or 1)
    except (TypeError, ValueError):
        return 'invalid_schedule_value'

    if frequency not in BACKUP_FREQUENCY_OPTIONS:
        return 'invalid_frequency'
    if times_per_period not in BACKUP_TIMES_PER_PERIOD_OPTIONS:
        return 'invalid_times_per_period'
    if run_hour < 0 or run_hour > 23:
        return 'invalid_run_hour'
    if run_minute < 0 or run_minute > 59:
        return 'invalid_run_minute'
    if retention_count < 1 or retention_count > 100:
        return 'invalid_retention_count'
    if frequency == 'Semanal' and day_of_week not in range(0, 7):
        return 'invalid_day_of_week'
    if frequency == 'Mensal' and day_of_month not in range(1, 32):
        return 'invalid_day_of_month'

    schedule = get_or_create_backup_schedule(user, default_retention_count)
    schedule.enabled = enabled
    schedule.frequency = frequency
    schedule.times_per_period = times_per_period
    schedule.day_of_week = day_of_week if frequency == 'Semanal' else None
    schedule.day_of_month = day_of_month if frequency == 'Mensal' else None
    schedule.run_hour = run_hour
    schedule.run_minute = run_minute
    schedule.retention_count = retention_count
    schedule.next_run_at = calculate_next_backup_run(schedule) if enabled else None

    try:
        record_activity(
            user,
            'backup',
            'backup_schedule_updated',
            'Rotina de backup atualizada com sucesso.',
            details={
                'enabled': enabled,
                'frequency': frequency,
                'times_per_period': times_per_period,
                'retention_count': retention_count,
            },
            commit=False,
        )
        db.session.commit()
        return None
    except Exception:
        db.session.rollback()
        return 'backup_schedule_persist_failed'


def run_backup_maintenance(app):
    with app.app_context():
        try:
            if not backup_schema_is_ready():
                app.logger.warning(
                    'Rotina de backups ignorada: schema incompleto. '
                    'Execute "flask db upgrade" antes de iniciar a manutencao.'
                )
                return {'processed_backups': 0, 'affected_users': 0, 'skipped': True}
        except Exception:
            app.logger.exception(
                'Falha ao validar o schema antes da rotina de backups.'
            )
            return {'processed_backups': 0, 'affected_users': 0, 'skipped': True}

        now = utcnow_naive()
        due_schedules = (
            BackupSchedule.query.filter_by(enabled=True)
            .filter(BackupSchedule.next_run_at.is_not(None))
            .filter(BackupSchedule.next_run_at <= now)
            .all()
        )
        processed_backups = 0
        affected_users = set()

        for schedule in due_schedules:
            user = db.session.get(User, schedule.user_id)
            if not user:
                continue
            try:
                create_backup_for_user(user, app, trigger_source='Automático', schedule=schedule)
                processed_backups += 1
                affected_users.add(user.id)
            except Exception:
                app.logger.exception(
                    'Falha ao executar backup automatico para user_id=%s.',
                    schedule.user_id,
                )

        if processed_backups > 0:
            app.logger.info(
                'Rotina de backups executada: %s backup(s) gerado(s) para %s usuario(s).',
                processed_backups,
                len(affected_users),
            )

        return {'processed_backups': processed_backups, 'affected_users': len(affected_users)}


def start_backup_scheduler(app):
    if app.config.get('TESTING') or not app.config.get('ENABLE_BACKUP_SCHEDULER', True):
        return None

    interval_seconds = max(
        int(app.config.get('BACKUP_SCHEDULER_INTERVAL_SECONDS', 300) or 300),
        60,
    )
    stop_event = threading.Event()

    def worker():
        while True:
            if stop_event.wait(interval_seconds):
                return
            try:
                run_backup_maintenance(app)
            except Exception:
                app.logger.exception('Falha na rotina agendada de backups.')

    thread = threading.Thread(
        target=worker,
        name='finora-backup-scheduler',
        daemon=True,
    )
    thread.start()
    return stop_event

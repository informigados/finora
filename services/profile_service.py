import os
import uuid
import json
import hashlib
import time

from flask import current_app
from flask_babel import gettext as _
from PIL import Image
from sqlalchemy import case, func, text
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
from urllib.parse import quote, urlencode

from database.db import db
from models.audit import ActivityLog, SystemEvent, UserSession
from models.backup import BackupRecord
from models.system import AppUpdateState
from models.time_utils import utcnow_naive
from models.user import User
from services.auth_service import is_strong_password, is_valid_email


DEFAULT_PROFILE_IMAGE = 'default_profile.svg'
ALLOWED_IMAGE_FORMATS = {'png', 'jpeg', 'jpg', 'gif'}
VALID_SESSION_TIMEOUT_OPTIONS = {0, 1, 2, 3, 4, 5, 10, 15, 30, 60}
DELETE_CONFIRMATION_TOKEN = 'EXCLUIR'  # nosec B105
SUPPORT_EMAIL = 'contato@informigados.com.br'
SESSION_TOUCH_INTERVAL_SECONDS = 60
SESSION_RECONCILIATION_LOOKBACK_SECONDS = 300
SESSION_END_REASON_LABELS = {
    None: 'Ativa',
    'logout': 'Encerrada por logout',
    'timeout': 'Encerrada por inatividade',
    'account_deleted': 'Encerrada por exclusão de conta',
    'replaced': 'Encerrada por reconciliação de sessão',
}
SYSTEM_EVENT_SEVERITY_LABELS = {
    'info': 'Informativo',
    'warning': 'Atenção',
    'error': 'Erro',
}
DETAIL_LABELS = {
    'category': 'Categoria',
    'subcategory': 'Subcategoria',
    'description': 'Descrição',
    'payment_method': 'Forma de pagamento/recebimento',
    'type': 'Tipo',
    'status': 'Status',
    'remember': 'Lembrar-me',
    'recurring': 'Recorrência',
    'file_name': 'Nome do arquivo',
    'trigger_source': 'Origem do disparo',
    'entries': 'Lançamentos',
    'year': 'Ano',
    'month': 'Mês',
    'delivery': 'Entrega',
    'error': 'Erro',
    'entry_id': 'Lançamento',
    'goal_id': 'Meta',
    'budget_id': 'Orçamento',
    'installed_version': 'Versão instalada',
    'channel': 'Canal',
    'backup_path': 'Backup',
    'package_path': 'Pacote',
    'recovery_key_version': 'Versão da chave',
    'session_timeout_minutes': 'Tempo de sessão',
}
DETAIL_VALUE_LABELS = {
    'Manual': 'Manual',
    'Automatic': 'Automático',
    'manual': 'Manual',
    'automatic': 'Automático',
    'none': 'Não informado',
    'email': 'E-mail',
    'resend': 'Reenvio',
    'register': 'Cadastro',
    'regenerate': 'Regeneração',
}
ACTIVITY_CATEGORY_LABELS = {
    'auth': 'Autenticação',
    'profile': 'Perfil',
    'entries': 'Lançamentos',
    'goals': 'Metas',
    'budgets': 'Orçamentos',
    'imports': 'Importações',
    'exports': 'Exportações',
    'backup': 'Backups',
    'system': 'Sistema',
}
ACTIVITY_TYPE_LABELS = {
    'login_success': 'Login realizado',
    'logout': 'Logout realizado',
    'session_timeout': 'Sessão expirada',
    'account_created': 'Conta criada',
    'profile_updated': 'Perfil atualizado',
    'password_changed': 'Senha alterada',
    'recovery_key_emailed': 'Chave reenviada',
    'recovery_key_regenerated': 'Chave regenerada',
    'entry_created': 'Lançamento criado',
    'entry_updated': 'Lançamento atualizado',
    'entry_deleted': 'Lançamento excluído',
    'goal_created': 'Meta criada',
    'goal_updated': 'Meta atualizada',
    'goal_deleted': 'Meta excluída',
    'budget_created': 'Orçamento criado',
    'budget_updated': 'Orçamento atualizado',
    'budget_deleted': 'Orçamento excluído',
    'import_completed': 'Importação concluída',
    'export_pdf': 'PDF exportado',
    'export_csv': 'CSV exportado',
    'export_txt': 'TXT exportado',
    'backup_generated': 'Backup gerado',
    'backup_deleted': 'Backup excluído',
    'backup_schedule_updated': 'Rotina de backup atualizada',
    'update_applied': 'Atualização aplicada',
}
SYSTEM_SOURCE_LABELS = {
    'entries': 'Lançamentos',
    'imports': 'Importações',
    'profile': 'Perfil',
    'update': 'Atualizações',
    'backup': 'Backups',
}
SYSTEM_UPDATE_STATUS_LABELS = {
    'idle': 'Pronto',
    'checking': 'Verificando',
    'available': 'Atualização disponível',
    'up_to_date': 'Atualizado',
    'not_configured': 'Não configurado',
    'applying': 'Aplicando atualização',
    'applied': 'Atualização aplicada',
    'error': 'Falha na atualização',
}


def _hash_session_token(raw_token):
    return hashlib.sha256((raw_token or '').encode('utf-8')).hexdigest()


def _serialize_details(details):
    if not details:
        return None
    return json.dumps(details, ensure_ascii=False, sort_keys=True, default=str)


def _deserialize_details(details_json):
    if not details_json:
        return None
    try:
        return json.loads(details_json)
    except (TypeError, ValueError):
        return {'raw': details_json}


def _request_ip_address(request_obj):
    trust_proxy_headers = False
    try:
        trust_proxy_headers = bool(current_app.config.get('TRUST_PROXY_HEADERS', False))
    except RuntimeError:
        trust_proxy_headers = False

    if trust_proxy_headers:
        forwarded_for = (request_obj.headers.get('X-Forwarded-For') or '').strip()
        if forwarded_for:
            return forwarded_for.split(',', 1)[0].strip()[:64]
        real_ip = (request_obj.headers.get('X-Real-IP') or '').strip()
        if real_ip:
            return real_ip[:64]
    return (request_obj.remote_addr or '')[:64] or None


def _request_user_agent(request_obj):
    return (request_obj.headers.get('User-Agent') or '')[:255] or None


def uploaded_file_size(file_storage):
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    return size


def is_valid_image(file_stream):
    try:
        current_pos = file_stream.tell()
        img = Image.open(file_stream)
        img.verify()
        image_format = (img.format or '').lower()
        file_stream.seek(current_pos)
        return image_format in ALLOWED_IMAGE_FORMATS
    except Exception:
        return False


def remove_profile_image_if_custom(root_path, filename):
    if not filename or filename == DEFAULT_PROFILE_IMAGE:
        return

    image_path = os.path.join(root_path, 'static', 'profile_pics', filename)
    if os.path.exists(image_path):
        os.remove(image_path)


def parse_session_timeout_minutes(raw_value):
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError('session_timeout') from exc

    if value not in VALID_SESSION_TIMEOUT_OPTIONS:
        raise ValueError('session_timeout')
    return value


def apply_profile_update(user, form, files, root_path, max_image_size):
    user.name = (form.get('name') or '').strip() or None
    new_email = (form.get('email') or '').strip().lower()
    raw_timeout = form.get('session_timeout_minutes', '0')

    try:
        user.session_timeout_minutes = parse_session_timeout_minutes(raw_timeout)
    except ValueError:
        return 'invalid_session_timeout'

    if new_email and new_email != user.email:
        if not is_valid_email(new_email):
            return 'invalid_email'

        existing_user = User.query.filter(
            User.email == new_email, User.id != user.id
        ).first()
        if existing_user:
            return 'duplicate_email'

        user.email = new_email

    if 'delete_image' in form:
        old_image = user.profile_image
        user.profile_image = DEFAULT_PROFILE_IMAGE
        remove_profile_image_if_custom(root_path, old_image)
    elif 'profile_image' in files:
        file = files['profile_image']
        if file and file.filename:
            if uploaded_file_size(file) > max_image_size:
                return 'image_too_large'

            if not is_valid_image(file.stream):
                return 'invalid_image'

            safe_original_name = secure_filename(file.filename)
            if not safe_original_name:
                return 'invalid_image_name'

            filename = f"user_{user.id}_{uuid.uuid4().hex[:8]}_{safe_original_name}"
            filepath = os.path.join(root_path, 'static', 'profile_pics', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)

            old_image = user.profile_image
            user.profile_image = filename
            remove_profile_image_if_custom(root_path, old_image)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return 'profile_persist_failed'

    return None


def change_user_password(user, current_password, new_password):
    if not user.check_password(current_password):
        return 'invalid_current_password'
    if not is_strong_password(new_password):
        return 'weak_password'

    user.set_password(new_password)
    user.bump_password_reset_version()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 'password_update_failed'

    return None


def delete_user_account(user, root_path):
    remove_profile_image_if_custom(root_path, user.profile_image)
    db.session.delete(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 'delete_account_failed'

    return None


def record_activity(
    user,
    event_category,
    event_type,
    message,
    details=None,
    ip_address=None,
    commit=True,
):
    try:
        activity = ActivityLog(
            user_id=getattr(user, 'id', None),
            event_category=event_category,
            event_type=event_type,
            message=message,
            details_json=_serialize_details(details),
            ip_address=(ip_address or None),
        )
        db.session.add(activity)
        if commit:
            db.session.commit()
        return activity
    except Exception:
        db.session.rollback()
        return None


def record_system_event(
    severity,
    source,
    message,
    user=None,
    event_code=None,
    details=None,
    commit=True,
):
    try:
        system_event = SystemEvent(
            user_id=getattr(user, 'id', None),
            severity=severity,
            source=source,
            event_code=event_code,
            message=message,
            details_json=_serialize_details(details),
        )
        db.session.add(system_event)
        if commit:
            db.session.commit()
        return system_event
    except Exception:
        db.session.rollback()
        return None


def start_user_session(user, request_obj, session_store):
    try:
        raw_token = uuid.uuid4().hex + uuid.uuid4().hex
        now = utcnow_naive()
        session_entry = UserSession(
            user_id=user.id,
            session_token_hash=_hash_session_token(raw_token),
            ip_address=_request_ip_address(request_obj),
            user_agent=_request_user_agent(request_obj),
            started_at=now,
            last_seen_at=now,
            is_current=True,
        )
        user.last_login_at = now
        db.session.add(session_entry)
        db.session.commit()
        session_store['audit_session_token'] = raw_token
        session_store['audit_session_id'] = session_entry.id
        session_store['audit_session_last_seen_ts'] = int(time.time())
        return session_entry
    except Exception:
        db.session.rollback()
        session_store.pop('audit_session_token', None)
        session_store.pop('audit_session_id', None)
        session_store.pop('audit_session_last_seen_ts', None)
        return None


def ensure_user_session(user, request_obj, session_store):
    raw_token = session_store.get('audit_session_token')
    if raw_token:
        return touch_user_session(user, session_store)

    try:
        now = utcnow_naive()
        recent_cutoff = now.timestamp() - SESSION_RECONCILIATION_LOOKBACK_SECONDS
        request_ip = _request_ip_address(request_obj)
        request_user_agent = _request_user_agent(request_obj)
        active_sessions = (
            UserSession.query.filter_by(
                user_id=user.id,
                is_current=True,
            )
            .order_by(UserSession.last_seen_at.desc(), UserSession.id.desc())
            .all()
        )

        reusable_session = None
        for active_session in active_sessions:
            last_seen_at = active_session.last_seen_at or active_session.started_at
            if last_seen_at and last_seen_at.timestamp() >= recent_cutoff:
                if (
                    active_session.ip_address == request_ip
                    and active_session.user_agent == request_user_agent
                ):
                    reusable_session = active_session
                    active_session.last_seen_at = now
                    continue
                active_session.last_seen_at = now
                active_session.ended_at = now
                active_session.ended_reason = 'replaced'
                active_session.is_current = False

        db.session.commit()
        if reusable_session is not None:
            session_store['audit_session_id'] = reusable_session.id
            session_store['audit_session_last_seen_ts'] = int(time.time())
            return reusable_session
    except Exception:
        db.session.rollback()

    return _start_user_session_without_login_bump(user, request_obj, session_store)


def _start_user_session_without_login_bump(user, request_obj, session_store):
    try:
        raw_token = uuid.uuid4().hex + uuid.uuid4().hex
        now = utcnow_naive()
        session_entry = UserSession(
            user_id=user.id,
            session_token_hash=_hash_session_token(raw_token),
            ip_address=_request_ip_address(request_obj),
            user_agent=_request_user_agent(request_obj),
            started_at=now,
            last_seen_at=now,
            is_current=True,
        )
        db.session.add(session_entry)
        db.session.commit()
        session_store['audit_session_token'] = raw_token
        session_store['audit_session_id'] = session_entry.id
        session_store['audit_session_last_seen_ts'] = int(time.time())
        return session_entry
    except Exception:
        db.session.rollback()
        session_store.pop('audit_session_token', None)
        session_store.pop('audit_session_id', None)
        session_store.pop('audit_session_last_seen_ts', None)
        return None


def touch_user_session(user, session_store):
    raw_token = session_store.get('audit_session_token')
    session_id = session_store.get('audit_session_id')
    if not raw_token and not session_id:
        return None

    now_ts = int(time.time())
    last_seen_ts = int(session_store.get('audit_session_last_seen_ts') or 0)
    if last_seen_ts and now_ts - last_seen_ts < SESSION_TOUCH_INTERVAL_SECONDS:
        return None

    try:
        if raw_token:
            session_entry = UserSession.query.filter_by(
                user_id=user.id,
                session_token_hash=_hash_session_token(raw_token),
                is_current=True,
            ).first()
        else:
            session_entry = UserSession.query.filter_by(
                user_id=user.id,
                id=session_id,
                is_current=True,
            ).first()
        if not session_entry:
            return None
        session_entry.last_seen_at = utcnow_naive()
        db.session.commit()
        session_store['audit_session_id'] = session_entry.id
        session_store['audit_session_last_seen_ts'] = now_ts
        return session_entry
    except Exception:
        db.session.rollback()
        return None


def end_user_session(user, session_store, reason):
    raw_token = session_store.get('audit_session_token')
    session_id = session_store.get('audit_session_id')
    session_store.pop('audit_session_token', None)
    session_store.pop('audit_session_id', None)
    session_store.pop('audit_session_last_seen_ts', None)

    if not raw_token and not session_id:
        return None

    try:
        if raw_token:
            session_entry = UserSession.query.filter_by(
                user_id=getattr(user, 'id', None),
                session_token_hash=_hash_session_token(raw_token),
                is_current=True,
            ).first()
        else:
            session_entry = UserSession.query.filter_by(
                user_id=getattr(user, 'id', None),
                id=session_id,
                is_current=True,
            ).first()
        if not session_entry:
            return None
        now = utcnow_naive()
        session_entry.last_seen_at = now
        session_entry.ended_at = now
        session_entry.ended_reason = reason
        session_entry.is_current = False
        db.session.commit()
        return session_entry
    except Exception:
        db.session.rollback()
        return None


def build_support_mailto(user, app_version, subject, message_prefix):
    body = (
        f"{_('Usuário')}: {user.username}\n"
        f"{_('E-mail')}: {user.email}\n"
        f"{_('Versão')}: {app_version}\n\n"
        f'{message_prefix}\n'
    )
    query = urlencode(
        {
            'subject': subject,
            'body': body,
        },
        quote_via=quote,
    )
    return f'mailto:{SUPPORT_EMAIL}?{query}'


def _humanize_identifier(raw_value):
    return str(raw_value).replace('_', ' ').strip().capitalize()


def _format_detail_label(key):
    return _(DETAIL_LABELS.get(key, _humanize_identifier(key)))


def _format_detail_value(key, value):
    if value is None or value == '':
        return _('Não informado')
    if isinstance(value, bool):
        return _('Sim') if value else _('Não')
    if isinstance(value, (int, float)):
        return str(value)

    normalized = str(value).strip()
    if not normalized:
        return _('Não informado')
    if normalized in DETAIL_VALUE_LABELS:
        return _(DETAIL_VALUE_LABELS[normalized])
    if normalized.lower() in DETAIL_VALUE_LABELS:
        return _(DETAIL_VALUE_LABELS[normalized.lower()])
    return _(normalized)


def _format_details_for_display(details):
    if not details:
        return []
    if isinstance(details, dict):
        return [
            {
                'label': _format_detail_label(str(key)),
                'value': _format_detail_value(str(key), value),
            }
            for key, value in details.items()
        ]
    if isinstance(details, list):
        return [{'label': _('Item'), 'value': _format_detail_value('item', value)} for value in details]
    return [{'label': _('Detalhe'), 'value': _format_detail_value('detail', details)}]


def _infer_device_label(user_agent):
    normalized = (user_agent or '').lower()
    if 'edg/' in normalized:
        return 'Microsoft Edge'
    if 'chrome/' in normalized and 'edg/' not in normalized:
        return 'Google Chrome'
    if 'firefox/' in normalized:
        return 'Mozilla Firefox'
    if 'safari/' in normalized and 'chrome/' not in normalized:
        return 'Safari'
    if 'waitress' in normalized:
        return 'Cliente local'
    if not user_agent:
        return 'Navegador não identificado'
    return user_agent


def _parse_page_number(raw_value):
    try:
        page = int(raw_value or 1)
    except (TypeError, ValueError):
        return 1
    return max(page, 1)


def _paginate_query(query, page, per_page):
    total = query.order_by(None).count()
    if total <= 0:
        return {
            'items': [],
            'page': 1,
            'per_page': per_page,
            'total': 0,
            'pages': 0,
            'has_prev': False,
            'has_next': False,
            'prev_page': None,
            'next_page': None,
        }

    pages = max((total + per_page - 1) // per_page, 1)
    safe_page = min(max(page, 1), pages)
    items = query.offset((safe_page - 1) * per_page).limit(per_page).all()
    return {
        'items': items,
        'page': safe_page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'has_prev': safe_page > 1,
        'has_next': safe_page < pages,
        'prev_page': safe_page - 1 if safe_page > 1 else None,
        'next_page': safe_page + 1 if safe_page < pages else None,
    }


def _build_pagination_links(page_data, page_param, tab_hash, query_overrides):
    links = dict(page_data)
    base_params = dict(query_overrides or {})
    links['tab_hash'] = tab_hash
    links['prev_url'] = None
    links['next_url'] = None

    if page_data['has_prev']:
        prev_params = {**base_params, page_param: page_data['prev_page']}
        links['prev_url'] = f'?{urlencode(prev_params)}{tab_hash}'
    if page_data['has_next']:
        next_params = {**base_params, page_param: page_data['next_page']}
        links['next_url'] = f'?{urlencode(next_params)}{tab_hash}'

    return links


def _build_system_health_summary(
    app_version,
    latest_backup,
    unresolved_system_events_count,
    app_update_state,
):
    from flask import current_app

    try:
        db.session.execute(text('SELECT 1'))
        database_status = {'label': 'Operacional', 'severity': 'success'}
    except Exception:
        db.session.rollback()
        database_status = {'label': 'Falha de conexão', 'severity': 'danger'}

    return {
        'database_status': database_status,
        'app_version': app_version,
        'backup_scheduler_enabled': bool(current_app.config.get('ENABLE_BACKUP_SCHEDULER', True)),
        'recurring_scheduler_enabled': bool(current_app.config.get('ENABLE_RECURRING_SCHEDULER', True)),
        'backup_storage_ready': os.path.isdir(current_app.config.get('BACKUP_STORAGE_DIR') or ''),
        'update_manifest_configured': bool(current_app.config.get('UPDATE_MANIFEST_URL') or ''),
        'update_status': getattr(app_update_state, 'status', 'idle') if app_update_state else 'idle',
        'update_status_label': _(
            SYSTEM_UPDATE_STATUS_LABELS.get(
                getattr(app_update_state, 'status', 'idle') if app_update_state else 'idle',
                'Desconhecido',
            )
        ),
        'recent_error_count': unresolved_system_events_count,
        'latest_backup_at': latest_backup.created_at if latest_backup else None,
        'latest_backup_name': latest_backup.file_name if latest_backup else None,
    }


def get_profile_hub_context(
    user,
    app_version,
    backup_retention_default,
    pagination_params=None,
    page_sizes=None,
):
    pagination_params = pagination_params or {}
    page_sizes = page_sizes or {}
    backup_page = _parse_page_number(pagination_params.get('backups_page'))
    sessions_page = _parse_page_number(pagination_params.get('sessions_page'))
    activities_page = _parse_page_number(pagination_params.get('activities_page'))
    events_page = _parse_page_number(pagination_params.get('events_page'))

    backup_per_page = int(page_sizes.get('backups', 10) or 10)
    sessions_per_page = int(page_sizes.get('sessions', 10) or 10)
    activities_per_page = int(page_sizes.get('activities', 15) or 15)
    events_per_page = int(page_sizes.get('events', 12) or 12)

    backup_schedule = user.backup_schedule
    if backup_schedule is None:
        backup_schedule = {
            'enabled': False,
            'frequency': 'Semanal',
            'times_per_period': 1,
            'retention_count': backup_retention_default,
            'next_run_at': None,
            'last_run_at': None,
        }

    backup_records_query = user.backup_records.order_by(BackupRecord.created_at.desc())
    login_sessions_query = user.login_sessions.order_by(UserSession.started_at.desc())
    activity_logs_query = user.activity_logs.order_by(ActivityLog.created_at.desc())
    system_events_query = (
        SystemEvent.query.filter(
            (SystemEvent.user_id == user.id) | (SystemEvent.user_id.is_(None))
        )
        .order_by(SystemEvent.created_at.desc())
    )

    backup_records_pagination = _paginate_query(
        backup_records_query,
        page=backup_page,
        per_page=backup_per_page,
    )
    login_sessions_pagination = _paginate_query(
        login_sessions_query,
        page=sessions_page,
        per_page=sessions_per_page,
    )
    activity_logs_pagination = _paginate_query(
        activity_logs_query,
        page=activities_page,
        per_page=activities_per_page,
    )
    system_events_pagination = _paginate_query(
        system_events_query,
        page=events_page,
        per_page=events_per_page,
    )

    backup_records = backup_records_pagination['items']
    login_sessions = login_sessions_pagination['items']
    activity_logs = activity_logs_pagination['items']
    system_events = system_events_pagination['items']
    app_update_state = (
        AppUpdateState.query.order_by(AppUpdateState.updated_at.desc(), AppUpdateState.id.desc()).first()
    )

    system_event_counts = db.session.query(
        func.count(SystemEvent.id),
        func.coalesce(
            func.sum(case((SystemEvent.resolved_at.is_(None), 1), else_=0)),
            0,
        ),
    ).filter(
        (SystemEvent.user_id == user.id) | (SystemEvent.user_id.is_(None))
    ).one()
    unresolved_system_events = int(system_event_counts[1] or 0)
    active_sessions_count = login_sessions_query.filter(UserSession.is_current.is_(True)).count()
    latest_backup = (
        backup_records[0]
        if backup_records and backup_records_pagination['page'] == 1
        else backup_records_query.limit(1).first()
    )
    session_history = [
        {
            'entry': entry,
            'device_label': _infer_device_label(entry.user_agent),
            'ended_reason_label': _(
                SESSION_END_REASON_LABELS.get(entry.ended_reason, entry.ended_reason or 'Ativa')
            ),
        }
        for entry in login_sessions
    ]
    activity_timeline = [
        {
            'entry': activity,
            'event_category_label': _(
                ACTIVITY_CATEGORY_LABELS.get(
                    activity.event_category,
                    _humanize_identifier(activity.event_category),
                )
            ),
            'event_type_label': _(
                ACTIVITY_TYPE_LABELS.get(
                    activity.event_type,
                    _humanize_identifier(activity.event_type),
                )
            ),
            'details': _format_details_for_display(_deserialize_details(activity.details_json)),
        }
        for activity in activity_logs
    ]
    system_event_timeline = [
        {
            'entry': event,
            'source_label': _(
                SYSTEM_SOURCE_LABELS.get(event.source, _humanize_identifier(event.source))
            ),
            'details': _format_details_for_display(_deserialize_details(event.details_json)),
            'severity_label': _(SYSTEM_EVENT_SEVERITY_LABELS.get(event.severity, event.severity)),
        }
        for event in system_events
    ]
    system_health = _build_system_health_summary(
        app_version,
        latest_backup,
        unresolved_system_events,
        app_update_state,
    )
    query_overrides = {
        'backups_page': backup_records_pagination['page'],
        'sessions_page': login_sessions_pagination['page'],
        'activities_page': activity_logs_pagination['page'],
        'events_page': system_events_pagination['page'],
    }

    return {
        'app_version': app_version,
        'backup_schedule': backup_schedule,
        'backup_records': backup_records,
        'login_sessions': login_sessions,
        'session_history': session_history,
        'activity_logs': activity_logs,
        'activity_timeline': activity_timeline,
        'system_events': system_events,
        'system_event_timeline': system_event_timeline,
        'backup_records_pagination': _build_pagination_links(
            backup_records_pagination,
            'backups_page',
            '#backups-pane',
            query_overrides,
        ),
        'session_history_pagination': _build_pagination_links(
            login_sessions_pagination,
            'sessions_page',
            '#sessions-pane',
            query_overrides,
        ),
        'activity_timeline_pagination': _build_pagination_links(
            activity_logs_pagination,
            'activities_page',
            '#activity-pane',
            query_overrides,
        ),
        'system_event_timeline_pagination': _build_pagination_links(
            system_events_pagination,
            'events_page',
            '#status-pane',
            query_overrides,
        ),
        'app_update_state': app_update_state,
        'system_health': system_health,
        'profile_hub_summary': {
            'backup_count': backup_records_pagination['total'],
            'active_sessions_count': active_sessions_count,
            'activity_count': activity_logs_pagination['total'],
            'open_system_events_count': unresolved_system_events,
        },
        'recovery_key_summary': {
            'version': int(user.recovery_key_version or 0),
            'generated_at': user.recovery_key_generated_at,
            'last_sent_at': user.recovery_key_last_sent_at,
            'current_key': user.get_recovery_key(),
        },
        'suggestion_mailto': build_support_mailto(
            user,
            app_version,
            _('Finora - Sugestão'),
            _('Descreva sua sugestão abaixo:'),
        ),
        'error_mailto': build_support_mailto(
            user,
            app_version,
            _('Finora - Comunicar erro'),
            _('Descreva o erro encontrado abaixo:'),
        ),
    }

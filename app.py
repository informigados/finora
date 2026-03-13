from datetime import datetime
from urllib.parse import urlparse

import click
import shutil
import tempfile
from flask import Flask, request, session, flash, redirect, url_for, g, jsonify
from flask_babel import Babel, gettext as _
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import inspect, text
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from database.db import db
from config import config
from extensions import limiter
from routes.dashboard import dashboard_bp
from routes.entries import entries_bp
from routes.export import export_bp
from routes.imports import import_bp
from routes.goals import goals_bp
from routes.budgets import budgets_bp
from routes.auth import auth_bp
from routes.backup import backup_bp
from routes.public import public_bp
from services.catalogs import DEFAULT_FINANCE_CATEGORIES
from services.db_resilience import run_idempotent_db_operation
from services.logging_utils import configure_application_logging, request_id_context
from services.maintenance_service import run_recurring_maintenance, start_recurring_scheduler
import os
from threading import Timer

import uuid
import time


RUNTIME_SQLITE_COLUMN_PATCHES = {
    'user': {
        'session_timeout_minutes': 'INTEGER NOT NULL DEFAULT 0',
        'failed_login_attempts': 'INTEGER NOT NULL DEFAULT 0',
        'locked_until': 'DATETIME',
    }
}

REQUIRED_APPLICATION_TABLES = frozenset(
    {'user', 'finances', 'goals', 'budgets', 'recurring_entries'}
)


CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "img-src 'self' data:",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    "font-src 'self' data: https://fonts.gstatic.com",
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
    "connect-src 'self'",
])


def ensure_runtime_schema_compatibility(app):
    """
    Applies safe runtime patches for legacy SQLite databases that were not
    migrated yet. This prevents runtime 500s on startup/login for known fields.
    """
    if app.config.get('TESTING'):
        return

    database_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not database_uri.startswith('sqlite'):
        return

    with app.app_context():
        try:
            inspector = inspect(db.engine)
            table_names = set(inspector.get_table_names())

            for table_name, required_columns in RUNTIME_SQLITE_COLUMN_PATCHES.items():
                if table_name not in table_names:
                    continue

                existing_columns = {
                    column['name'] for column in inspector.get_columns(table_name)
                }

                for column_name, column_definition in required_columns.items():
                    if column_name in existing_columns:
                        continue

                    statement = (
                        f'ALTER TABLE "{table_name}" '
                        f'ADD COLUMN "{column_name}" {column_definition}'
                    )
                    db.session.execute(text(statement))
                    db.session.commit()
                    app.logger.warning(
                        'Compatibilidade aplicada: coluna %s.%s criada em runtime.',
                        table_name,
                        column_name,
                    )
        except Exception:
            db.session.rollback()
            app.logger.exception(
                'Falha ao aplicar patches de compatibilidade de schema em runtime.'
            )


def _resolve_sqlite_database_path(app):
    database_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not database_uri.startswith('sqlite:///'):
        return None

    db_path = database_uri.replace('sqlite:///', '', 1)
    if not db_path or db_path == ':memory:':
        return None

    if os.path.isabs(db_path):
        return db_path

    return os.path.join(app.root_path, db_path)


def _build_alembic_config(app):
    migrations_dir = os.path.join(app.root_path, 'migrations')
    alembic_config = AlembicConfig(os.path.join(migrations_dir, 'alembic.ini'))
    alembic_config.set_main_option('script_location', migrations_dir.replace('%', '%%'))
    alembic_config.set_main_option(
        'sqlalchemy.url',
        app.config['SQLALCHEMY_DATABASE_URI'].replace('%', '%%'),
    )
    return alembic_config


def _get_alembic_head_revision(app):
    return ScriptDirectory.from_config(_build_alembic_config(app)).get_current_head()


def _stamp_alembic_head(app):
    head_revision = _get_alembic_head_revision(app)
    with db.engine.begin() as connection:
        connection.execute(
            text(
                'CREATE TABLE IF NOT EXISTS alembic_version '
                '(version_num VARCHAR(32) NOT NULL)'
            )
        )
        connection.execute(text('DELETE FROM alembic_version'))
        connection.execute(
            text('INSERT INTO alembic_version (version_num) VALUES (:version_num)'),
            {'version_num': head_revision},
        )


def ensure_sqlite_schema_bootstrapped(app):
    if app.config.get('TESTING'):
        return

    db_path = _resolve_sqlite_database_path(app)
    if not db_path:
        return

    with app.app_context():
        try:
            table_names = set(inspect(db.engine).get_table_names())
        except Exception:
            app.logger.exception('Falha ao inspecionar schema SQLite na inicializacao.')
            return

        if REQUIRED_APPLICATION_TABLES.issubset(table_names):
            return

        application_tables_present = table_names.intersection(REQUIRED_APPLICATION_TABLES)
        if application_tables_present:
            missing_tables = sorted(REQUIRED_APPLICATION_TABLES.difference(table_names))
            app.logger.error(
                'Schema SQLite incompleto detectado. Tabelas ausentes: %s. '
                'Execute "flask db upgrade" ou restaure um backup valido.',
                ', '.join(missing_tables),
            )
            return

        if table_names not in (set(), {'alembic_version'}):
            app.logger.error(
                'Schema SQLite inconsistente detectado com tabelas inesperadas: %s.',
                ', '.join(sorted(table_names)),
            )
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        repair_backup_path = f'{db_path}.bootstrap_repair_{timestamp}.bak'

        try:
            db.session.remove()
            db.engine.dispose()

            if os.path.exists(db_path):
                shutil.copy2(db_path, repair_backup_path)
                os.remove(db_path)
                app.logger.warning(
                    'Banco SQLite inconsistente detectado. Backup criado em %s antes do reparo.',
                    repair_backup_path,
                )

            db.create_all()
            _stamp_alembic_head(app)
            db.engine.dispose()
            repaired_tables = set(inspect(db.engine).get_table_names())
        except Exception:
            app.logger.exception(
                'Falha ao reparar automaticamente o schema SQLite local.'
            )
            return

        if REQUIRED_APPLICATION_TABLES.issubset(repaired_tables):
            app.logger.info(
                'Schema SQLite local reparado com sucesso via bootstrap Alembic.'
            )
            return

        app.logger.error(
            'Reparo automatico do schema SQLite nao concluiu todas as tabelas esperadas.'
        )


def seed_default_user(app):
    if app.config.get('TESTING') or not app.config.get('ENABLE_DEFAULT_USER_SEED'):
        return

    with app.app_context():
        from models.user import User
        from sqlalchemy.exc import OperationalError
        
        try:
            username = os.environ.get('DEFAULT_USER_USERNAME', 'admin')
            email = os.environ.get('DEFAULT_USER_EMAIL', 'admin@finora.local')
            name = os.environ.get('DEFAULT_USER_NAME', 'Administrador de Teste')
            password = os.environ.get('DEFAULT_USER_PASSWORD')

            if not password:
                app.logger.warning(
                    "DEFAULT_USER_PASSWORD não configurada; seed de usuário padrão ignorado."
                )
                return

            user = User.query.filter_by(username=username).first()
            if not user:
                app.logger.info("Criando usuário padrão de desenvolvimento.")
                default_user = User(
                    username=username,
                    email=email,
                    name=name
                )
                default_user.set_password(password)
                recovery_key = str(uuid.uuid4()).replace('-', '').upper()[:16]
                default_user.set_recovery_key(recovery_key)
                
                db.session.add(default_user)
                db.session.commit()
                app.logger.info(
                    "Usuário padrão criado com sucesso. username=%s email=%s",
                    username,
                    email,
                )
            else:
                app.logger.info(
                    "Usuário padrão já existente; seed ignorado. username=%s",
                    username,
                )
        except OperationalError:
            app.logger.debug(
                'Seed de usuário padrão ignorado: tabelas ainda indisponíveis.'
            )
        except Exception as e:
            db.session.rollback()
            app.logger.exception("Erro ao criar usuário padrão: %s", e)

def get_locale():
    # Check if user has set a language in session
    if 'lang' in session:
        return session['lang']
    # Otherwise try to match best language from request
    return request.accept_languages.best_match(['pt', 'en', 'es'])

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    configure_application_logging(app)

    if config_name == 'production' and not app.config.get('SECRET_KEY'):
        raise RuntimeError(
            'SECRET_KEY não configurada. Defina SECRET_KEY para iniciar em produção.'
        )
    
    # Babel configuration
    Babel(app, locale_selector=get_locale)
    
    # CSRF Protection
    CSRFProtect(app)

    limiter.init_app(app)
    
    db.init_app(app)
    
    # Import models so Alembic can detect them
    from models.user import User
    import models.budget  # noqa: F401
    import models.finance  # noqa: F401
    import models.goal  # noqa: F401
    import models.recurring  # noqa: F401
    
    Migrate(app, db)
    
    # Login Manager configuration
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = _('Por favor, faça login para acessar esta página.')
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)
    
    # from models.user import User # Already imported above
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.before_request
    def enforce_session_timeout():
        request_id = (
            request.headers.get(app.config.get('REQUEST_ID_HEADER', 'X-Request-ID'))
            or request.headers.get('X-Correlation-ID')
            or uuid.uuid4().hex
        )
        g.request_id = request_id
        g.request_id_token = request_id_context.set(request_id)
        g.session_timeout_minutes = 0
        g.session_expires_at = None

        if (
            request.method == 'GET'
            and request.endpoint not in {None, 'set_language', 'health', 'favicon'}
            and not (request.endpoint or '').startswith('static')
        ):
            session['language_redirect_target'] = request.full_path.rstrip('?')

        if not current_user.is_authenticated:
            return None

        timeout_minutes = int(getattr(current_user, 'session_timeout_minutes', 0) or 0)
        if timeout_minutes <= 0:
            session.pop('last_activity_ts', None)
            return None

        now_ts = int(time.time())
        last_activity_ts = int(session.get('last_activity_ts') or now_ts)
        timeout_seconds = timeout_minutes * 60

        if now_ts - last_activity_ts >= timeout_seconds:
            logout_user()
            session.clear()
            flash(_('Sessão expirada por inatividade. Faça login novamente.'), 'warning')
            return redirect(url_for('auth.login'))

        session['last_activity_ts'] = now_ts
        session.modified = True
        g.session_timeout_minutes = timeout_minutes
        g.session_expires_at = now_ts + timeout_seconds
        return None

    @app.context_processor
    def inject_globals():
        return {
            'current_year': datetime.now().year,
            'session_timeout_minutes': getattr(g, 'session_timeout_minutes', 0),
            'session_expires_at': getattr(g, 'session_expires_at', None),
            'default_finance_categories': DEFAULT_FINANCE_CATEGORIES,
        }

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault(
            app.config.get('REQUEST_ID_HEADER', 'X-Request-ID'),
            getattr(g, 'request_id', '-'),
        )
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(), microphone=(), geolocation=()',
        )
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        response.headers.setdefault('Content-Security-Policy', CONTENT_SECURITY_POLICY)

        if (
            app.config.get('SESSION_COOKIE_SECURE')
            and request.is_secure
            and request.host.split(':', 1)[0] not in {'127.0.0.1', 'localhost'}
        ):
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )

        return response

    @app.teardown_request
    def reset_request_context(_error=None):
        token = getattr(g, 'request_id_token', None)
        if token is not None:
            g.request_id_token = None
            try:
                request_id_context.reset(token)
            except RuntimeError:
                app.logger.debug(
                    'Contexto de request_id ja havia sido encerrado durante o teardown.'
                )
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(entries_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(budgets_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(public_bp)

    def _get_safe_local_redirect_target(target: str | None) -> str | None:
        if not target:
            return None

        redirect_url = urlparse(target)
        if redirect_url.scheme or redirect_url.netloc:
            return None
        if not redirect_url.path.startswith('/'):
            return None

        local_target = redirect_url.path
        if redirect_url.query:
            local_target = f'{local_target}?{redirect_url.query}'
        if redirect_url.fragment:
            local_target = f'{local_target}#{redirect_url.fragment}'
        return local_target

    @app.route('/set_language/<lang_code>')
    def set_language(lang_code):
        if lang_code in ['pt', 'en', 'es']:
            session['lang'] = lang_code
            flash(_('Idioma alterado com sucesso!'), 'success')
        fallback = url_for('public.welcome')
        redirect_target = _get_safe_local_redirect_target(
            session.get('language_redirect_target')
        )
        if redirect_target:
            return redirect(redirect_target)
        return redirect(fallback)

    @app.route('/favicon.ico')
    def favicon():
        return redirect(url_for('static', filename='favicon.svg', v='20260302e'))

    @app.route('/health')
    def health():
        try:
            run_idempotent_db_operation(lambda: db.session.execute(text('SELECT 1')))
            return jsonify({'status': 'ok', 'database': 'ok'}), 200
        except Exception:
            db.session.rollback()
            app.logger.exception('Falha no health check do banco de dados.')
            return jsonify({'status': 'degraded', 'database': 'error'}), 503

    @app.cli.command('process-recurring')
    @click.option('--quiet', is_flag=True, help='Reduz a saída textual do comando.')
    def process_recurring_command(quiet):
        result = run_recurring_maintenance(app)
        if not quiet:
            click.echo(
                'Recurring maintenance complete: '
                f"{result['processed_entries']} entries for {result['affected_users']} user(s)."
            )
        
    ensure_sqlite_schema_bootstrapped(app)
    ensure_runtime_schema_compatibility(app)
    seed_default_user(app)

    return app

def find_free_port(start_port=5000):
    import socket
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except socket.error:
                port += 1
    return start_port


def _browser_launch_guard_path(port):
    return os.path.join(
        tempfile.gettempdir(),
        f'finora_browser_launch_{port}.lock',
    )


def _acquire_browser_launch_guard(port, ttl_seconds=15):
    guard_path = _browser_launch_guard_path(port)
    now = time.time()

    try:
        if os.path.exists(guard_path):
            age_seconds = now - os.path.getmtime(guard_path)
            if age_seconds < ttl_seconds:
                return False

        with open(guard_path, 'w', encoding='utf-8') as guard_file:
            guard_file.write(str(now))
    except OSError:
        return True

    return True


def open_browser(port):
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{port}/", new=0, autoraise=True)


def schedule_browser_open(port, delay_seconds=1.5):
    auto_open_enabled = os.environ.get('FINORA_AUTO_OPEN_BROWSER', '1').strip().lower()
    if auto_open_enabled not in {'1', 'true', 'yes', 'on'}:
        return False

    if not _acquire_browser_launch_guard(port):
        return False

    Timer(delay_seconds, lambda: open_browser(port)).start()
    return True

if __name__ == '__main__':
    from waitress import serve
    
    # Production mode check (simple heuristic or env var)
    env_config = os.environ.get('FLASK_ENV', 'development')
    app = create_app(env_config if env_config in config else 'default')
    port = find_free_port(5000)

    if env_config == 'production':
        run_recurring_maintenance(app)
        start_recurring_scheduler(app)
        print(f"Starting FINORA in PRODUCTION mode on port {port}...")
        print(f"Access at http://127.0.0.1:{port}")
        schedule_browser_open(port)
        serve(app, host='127.0.0.1', port=port)
    else:
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            run_recurring_maintenance(app)
            start_recurring_scheduler(app)
        else:
            schedule_browser_open(port)
        app.run(host='127.0.0.1', port=port, debug=app.config.get('DEBUG', False))

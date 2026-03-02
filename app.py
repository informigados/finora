from datetime import datetime
from urllib.parse import urlparse

from flask import Flask, request, session, flash, redirect, url_for, g
from flask_babel import Babel, gettext as _
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import inspect, text
from database.db import db
from config import config
from routes.dashboard import dashboard_bp
from routes.entries import entries_bp
from routes.export import export_bp
from routes.imports import import_bp
from routes.goals import goals_bp
from routes.budgets import budgets_bp
from routes.auth import auth_bp
from routes.backup import backup_bp
from routes.public import public_bp
import os
from threading import Timer

import uuid
import time


RUNTIME_SQLITE_COLUMN_PATCHES = {
    'user': {
        'session_timeout_minutes': 'INTEGER NOT NULL DEFAULT 0',
    }
}


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


def seed_default_user(app):
    if app.config.get('TESTING') or not app.config.get('ENABLE_DEFAULT_USER_SEED'):
        return

    with app.app_context():
        from models.user import User
        from sqlalchemy.exc import OperationalError
        
        try:
            username = os.environ.get('DEFAULT_USER_USERNAME', 'example')
            email = os.environ.get('DEFAULT_USER_EMAIL', 'user@example.com.br')
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
                    name='Usuário Exemplo'
                )
                default_user.set_password(password)
                recovery_key = str(uuid.uuid4()).replace('-', '').upper()[:16]
                default_user.set_recovery_key(recovery_key)
                
                db.session.add(default_user)
                db.session.commit()
                app.logger.info("Usuário padrão criado com sucesso.")
        except OperationalError:
            # Tables likely don't exist yet (e.g. before first migration)
            pass
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

    if config_name == 'production' and not app.config.get('SECRET_KEY'):
        raise RuntimeError(
            'SECRET_KEY não configurada. Defina SECRET_KEY para iniciar em produção.'
        )
    
    # Babel configuration
    babel = Babel(app, locale_selector=get_locale)
    
    # CSRF Protection
    csrf = CSRFProtect(app)
    
    db.init_app(app)
    
    # Import models so Alembic can detect them
    from models.user import User
    from models.finance import Finance
    from models.goal import Goal
    from models.recurring import RecurringEntry
    from models.budget import Budget
    
    migrate = Migrate(app, db)
    
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
        g.session_timeout_minutes = 0
        g.session_expires_at = None

        if not current_user.is_authenticated:
            return

        timeout_minutes = int(getattr(current_user, 'session_timeout_minutes', 0) or 0)
        if timeout_minutes <= 0:
            session.pop('last_activity_ts', None)
            return

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

    @app.context_processor
    def inject_globals():
        return {
            'current_year': datetime.now().year,
            'session_timeout_minutes': getattr(g, 'session_timeout_minutes', 0),
            'session_expires_at': getattr(g, 'session_expires_at', None),
        }
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(entries_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(budgets_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(public_bp)
    
    # with app.app_context():
    #     # Import models to ensure tables are created
    #     from models.finance import Finance
    #     from models.goal import Goal
    #     from models.recurring import RecurringEntry
    #     from models.budget import Budget
    #     db.create_all()

    def _is_safe_redirect(target: str | None) -> bool:
        if not target:
            return False
        host_url = urlparse(request.host_url)
        redirect_url = urlparse(target)
        return (
            redirect_url.scheme in ('http', 'https', '')
            and (not redirect_url.netloc or redirect_url.netloc == host_url.netloc)
        )

    @app.route('/set_language/<lang_code>')
    def set_language(lang_code):
        if lang_code in ['pt', 'en', 'es']:
            session['lang'] = lang_code
            flash(_('Idioma alterado com sucesso!'), 'success')
        fallback = url_for('public.welcome')
        if _is_safe_redirect(request.referrer):
            return redirect(request.referrer)
        return redirect(fallback)

    @app.route('/favicon.ico')
    def favicon():
        return redirect(url_for('static', filename='favicon.svg', v='20260302e'))
        
    # Seed default user if not exists
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

def open_browser(port):
    import webbrowser
    webbrowser.open_new(f"http://127.0.0.1:{port}/")

if __name__ == '__main__':
    from waitress import serve
    
    # Production mode check (simple heuristic or env var)
    env_config = os.environ.get('FLASK_ENV', 'development')
    app = create_app(env_config if env_config in config else 'default')
    
    port = find_free_port(5000)
    
    if env_config == 'production':
        print(f"Starting FINORA in PRODUCTION mode on port {port}...")
        print(f"Access at http://127.0.0.1:{port}")
        Timer(1.5, lambda: open_browser(port)).start()
        serve(app, host='127.0.0.1', port=port)
    else:
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            pass 
        else:
            Timer(1.5, lambda: open_browser(port)).start()
        app.run(host='127.0.0.1', port=port, debug=True)

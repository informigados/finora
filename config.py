import os
import secrets
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))
LOCAL_SECRET_KEY_PATH = os.path.join(basedir, 'database', '.finora_secret_key')
DEFAULT_UPDATE_MANIFEST_PATH = os.path.join(basedir, 'updates', 'manifest.json')


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_int(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_or_create_local_secret_key():
    secret_key = os.environ.get('SECRET_KEY')
    if secret_key:
        return secret_key

    try:
        if os.path.exists(LOCAL_SECRET_KEY_PATH):
            with open(LOCAL_SECRET_KEY_PATH, encoding='utf-8') as secret_file:
                existing_secret = secret_file.read().strip()
                if existing_secret:
                    return existing_secret
    except OSError:
        pass

    generated_secret = secrets.token_urlsafe(48)
    try:
        os.makedirs(os.path.dirname(LOCAL_SECRET_KEY_PATH), exist_ok=True)
        with open(LOCAL_SECRET_KEY_PATH, 'w', encoding='utf-8') as secret_file:
            secret_file.write(generated_secret)
    except OSError:
        return generated_secret

    return generated_secret

class Config:
    APP_VERSION = os.environ.get('APP_VERSION', '1.3.0')
    APP_BASE_URL = os.environ.get('APP_BASE_URL', '')
    APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'America/Sao_Paulo')
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    BABEL_DEFAULT_LOCALE = 'pt'
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    MAX_IMPORT_ROWS = 20000
    MAX_PROFILE_IMAGE_SIZE = 2 * 1024 * 1024  # 2 MB
    ENABLE_DEFAULT_USER_SEED = _env_flag('ENABLE_DEFAULT_USER_SEED', default=False)
    AUTH_MAX_FAILED_LOGINS = 5
    AUTH_LOCKOUT_MINUTES = 15
    AUTH_RATE_LIMIT_LOGIN = '10 per 5 minutes'
    AUTH_RATE_LIMIT_REGISTER = '5 per hour'
    AUTH_RATE_LIMIT_FORGOT_PASSWORD = '10 per hour'  # nosec B105
    AUTH_RATE_LIMIT_LOOKUPS = '30 per minute'
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    ENABLE_RECURRING_SCHEDULER = True
    RECURRING_PROCESS_INTERVAL_SECONDS = 300
    ENABLE_BACKUP_SCHEDULER = _env_flag('ENABLE_BACKUP_SCHEDULER', default=True)
    DB_IDEMPOTENT_MAX_RETRIES = 2
    DB_IDEMPOTENT_RETRY_BACKOFF_SECONDS = 0.15
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    SQLALCHEMY_LOG_LEVEL = os.environ.get('SQLALCHEMY_LOG_LEVEL', 'WARNING')
    WERKZEUG_LOG_LEVEL = os.environ.get('WERKZEUG_LOG_LEVEL', 'INFO')
    WAITRESS_LOG_LEVEL = os.environ.get('WAITRESS_LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.environ.get(
        'LOG_FORMAT',
        '[%(asctime)s] %(levelname)s %(name)s request_id=%(request_id)s %(message)s',
    )
    REQUEST_ID_HEADER = 'X-Request-ID'
    LOG_TO_FILE = _env_flag('LOG_TO_FILE', default=False)
    LOG_DIRECTORY = os.environ.get('LOG_DIRECTORY') or os.path.join(basedir, 'logs')
    LOG_FILE_NAME = os.environ.get('LOG_FILE_NAME', 'finora.log')
    LOG_MAX_BYTES = _env_int('LOG_MAX_BYTES', 1_048_576)
    LOG_BACKUP_COUNT = _env_int('LOG_BACKUP_COUNT', 5)
    BACKUP_STORAGE_DIR = os.environ.get('BACKUP_STORAGE_DIR') or os.path.join(basedir, 'backups')
    BACKUP_SCHEDULER_INTERVAL_SECONDS = _env_int('BACKUP_SCHEDULER_INTERVAL_SECONDS', 300)
    BACKUP_DEFAULT_RETENTION_COUNT = _env_int('BACKUP_DEFAULT_RETENTION_COUNT', 20)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = _env_int('MAIL_PORT', 587)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_USE_TLS = _env_flag('MAIL_USE_TLS', default=True)
    MAIL_USE_SSL = _env_flag('MAIL_USE_SSL', default=False)
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')
    MAIL_FROM_NAME = os.environ.get('MAIL_FROM_NAME', 'Finora')
    MAIL_TIMEOUT_SECONDS = _env_int('MAIL_TIMEOUT_SECONDS', 10)
    UPDATE_CHANNEL = os.environ.get('UPDATE_CHANNEL', 'stable')
    UPDATE_MANIFEST_URL = os.environ.get('UPDATE_MANIFEST_URL') or DEFAULT_UPDATE_MANIFEST_PATH
    UPDATE_DOWNLOAD_DIR = os.environ.get('UPDATE_DOWNLOAD_DIR') or os.path.join(basedir, 'updates')
    UPDATE_TARGET_ROOT = os.environ.get('UPDATE_TARGET_ROOT') or basedir
    UPDATE_CHECK_TIMEOUT_SECONDS = _env_int('UPDATE_CHECK_TIMEOUT_SECONDS', 10)
    UPDATE_ALLOW_LOCAL_ASSETS = _env_flag('UPDATE_ALLOW_LOCAL_ASSETS', default=False)
    ACTIVITY_LOG_RETENTION_DAYS = _env_int('ACTIVITY_LOG_RETENTION_DAYS', 180)
    SYSTEM_EVENT_RETENTION_DAYS = _env_int('SYSTEM_EVENT_RETENTION_DAYS', 90)
    TRUST_PROXY_HEADERS = _env_flag('TRUST_PROXY_HEADERS', default=False)
    RECURRING_MAX_CATCH_UP_RUNS = _env_int('RECURRING_MAX_CATCH_UP_RUNS', 90)
    PROFILE_BACKUPS_PAGE_SIZE = _env_int('PROFILE_BACKUPS_PAGE_SIZE', 10)
    PROFILE_SESSIONS_PAGE_SIZE = _env_int('PROFILE_SESSIONS_PAGE_SIZE', 10)
    PROFILE_ACTIVITIES_PAGE_SIZE = _env_int('PROFILE_ACTIVITIES_PAGE_SIZE', 15)
    PROFILE_SYSTEM_EVENTS_PAGE_SIZE = _env_int('PROFILE_SYSTEM_EVENTS_PAGE_SIZE', 12)
    PDF_EXPORT_MAX_ROWS = _env_int('PDF_EXPORT_MAX_ROWS', 5000)

class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'database', 'finora.db')

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'database', 'finora.db')
    LOG_TO_FILE = _env_flag('LOG_TO_FILE', default=True)
    
    # Security headers and other production settings can be added here
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = 'test_secret_key'  # nosec B105
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    ENABLE_DEFAULT_USER_SEED = False
    AUTH_RATE_LIMIT_LOGIN = '100 per minute'
    AUTH_RATE_LIMIT_REGISTER = '100 per minute'
    AUTH_RATE_LIMIT_FORGOT_PASSWORD = '100 per minute'  # nosec B105
    AUTH_RATE_LIMIT_LOOKUPS = '300 per minute'
    ENABLE_RECURRING_SCHEDULER = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

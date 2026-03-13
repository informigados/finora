import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


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

class Config:
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
    ENABLE_RECURRING_SCHEDULER = True
    RECURRING_PROCESS_INTERVAL_SECONDS = 300
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

class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_key_finora_fallback'
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

import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

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
    ENABLE_DEFAULT_USER_SEED = False

class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_key_finora_fallback'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'database', 'finora.db')
    ENABLE_DEFAULT_USER_SEED = os.environ.get('ENABLE_DEFAULT_USER_SEED') == '1'

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'database', 'finora.db')
    
    # Security headers and other production settings can be added here
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = 'test_secret_key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    ENABLE_DEFAULT_USER_SEED = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

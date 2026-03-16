import pytest
from app import create_app
from config import Config, DEFAULT_UPDATE_MANIFEST_PATH, DevelopmentConfig, ProductionConfig
from database.db import db
from models.user import User


@pytest.fixture(autouse=True)
def isolate_runtime_config(tmp_path, monkeypatch):
    temp_db_path = (tmp_path / 'finora-test-runtime.db').as_posix()
    temp_backup_dir = str(tmp_path / 'backups')
    temp_update_dir = str(tmp_path / 'updates')
    temp_log_dir = str(tmp_path / 'logs')
    temp_target_root = str(tmp_path / 'target-root')

    monkeypatch.setattr(
        DevelopmentConfig,
        'SQLALCHEMY_DATABASE_URI',
        f'sqlite:///{temp_db_path}',
    )
    monkeypatch.setattr(
        ProductionConfig,
        'SQLALCHEMY_DATABASE_URI',
        f'sqlite:///{temp_db_path}',
    )

    for cfg in (Config, DevelopmentConfig, ProductionConfig):
        monkeypatch.setattr(cfg, 'ENABLE_DEFAULT_USER_SEED', False, raising=False)
        monkeypatch.setattr(cfg, 'ENABLE_RECURRING_SCHEDULER', False, raising=False)
        monkeypatch.setattr(cfg, 'ENABLE_BACKUP_SCHEDULER', False, raising=False)
        monkeypatch.setattr(cfg, 'LOG_TO_FILE', False, raising=False)
        monkeypatch.setattr(cfg, 'BACKUP_STORAGE_DIR', temp_backup_dir, raising=False)
        monkeypatch.setattr(cfg, 'UPDATE_DOWNLOAD_DIR', temp_update_dir, raising=False)
        monkeypatch.setattr(cfg, 'UPDATE_TARGET_ROOT', temp_target_root, raising=False)
        monkeypatch.setattr(cfg, 'UPDATE_MANIFEST_URL', DEFAULT_UPDATE_MANIFEST_PATH, raising=False)
        monkeypatch.setattr(cfg, 'LOG_DIRECTORY', temp_log_dir, raising=False)

@pytest.fixture
def app():
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def auth_client(client, app):
    # Create a user
    with app.app_context():
        user = User(username='testuser', email='test@example.com', name='Test User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    # Login
    client.post('/login', data={
        'identifier': 'testuser',
        'password': 'Password123'
    }, follow_redirects=True)
    
    return client

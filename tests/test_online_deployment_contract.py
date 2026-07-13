from pathlib import Path


def test_docker_image_runs_migrations_as_non_root_and_exposes_healthcheck():
    dockerfile = Path('Dockerfile').read_text(encoding='utf-8')
    assert 'default-libmysqlclient-dev' in dockerfile
    assert 'USER finora' in dockerfile
    assert 'flask db upgrade' in dockerfile
    assert 'gunicorn --bind 0.0.0.0:5000' in dockerfile
    assert "http://127.0.0.1:5000/health" in dockerfile


def test_compose_requires_secrets_and_waits_for_mysql_health():
    compose = Path('docker-compose.yml').read_text(encoding='utf-8')
    assert 'mysql:8.4' in compose
    assert 'condition: service_healthy' in compose
    assert 'SECRET_KEY: ${SECRET_KEY:?' in compose
    assert 'DATABASE_URL: ${DATABASE_URL:?' in compose
    assert 'MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:?' in compose
    assert 'ENABLE_DEFAULT_USER_SEED: "0"' in compose
    assert 'mysql_data:/var/lib/mysql' in compose
    assert 'finora_profiles:/app/static/profile_pics' in compose


def test_online_example_uses_the_installed_mysql_driver_without_real_secrets():
    example = Path('.env.example').read_text(encoding='utf-8')
    requirements = Path('requirements.txt').read_text(encoding='utf-8')
    assert 'mysqlclient==' in requirements
    assert 'mysql+mysqldb://' in example
    assert 'mysql+pymysql://' not in example
    assert 'ENABLE_DEFAULT_USER_SEED=0' in example
    assert 'MAIL_PASSWORD=\n' in example


def test_docker_context_excludes_local_secrets_and_runtime_data():
    ignored = Path('.dockerignore').read_text(encoding='utf-8')
    for expected in ('.env', '.venv', 'database/*.db', 'backups', 'logs'):
        assert expected in ignored

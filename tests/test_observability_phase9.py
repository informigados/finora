import io
from datetime import datetime

from werkzeug.datastructures import FileStorage

from database.db import db
from models.backup import BackupRecord
from models.audit import ActivityLog, SystemEvent, UserSession
from models.user import User


def _login(client, username, password='Password123'):
    return client.post(
        '/login',
        data={'identifier': username, 'password': password},
        follow_redirects=True,
    )


def test_business_actions_are_written_to_activity_history(client, app):
    with app.app_context():
        user = User(username='observability', email='observability@example.com', name='Observability User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    _login(client, 'observability')

    client.post(
        '/entries/add',
        data={
            'description': 'Salario',
            'value': '5000',
            'category': 'Trabalho',
            'subcategory': 'Salário',
            'type': 'Receita',
            'status': 'Pago',
            'due_date': '2026-03-10',
            'payment_method': 'Transferência / PIX',
        },
        follow_redirects=True,
    )

    client.post(
        '/goals/add',
        data={'name': 'Reserva', 'target_amount': '1000', 'current_amount': '100'},
        follow_redirects=True,
    )

    client.post(
        '/budgets/add',
        data={'category': 'Lazer', 'limit_amount': '300', 'period': 'Mensal'},
        follow_redirects=True,
    )

    upload = FileStorage(
        stream=io.BytesIO(
            'descricao,valor,categoria,subcategoria,tipo,status,data,forma_pagamento\n'
            'Freela,10.50,Trabalho,Freelance / Serviços,Receita,Pago,2026-03-11,PIX\n'.encode('utf-8')
        ),
        filename='observability.csv',
    )
    client.post(
        '/import',
        data={'file': upload},
        content_type='multipart/form-data',
        follow_redirects=True,
    )

    client.get('/export/csv/2026/3', follow_redirects=True)

    with app.app_context():
        event_types = {
            log.event_type
            for log in ActivityLog.query.filter_by(event_category='entries').all()
        }
        all_event_types = {
            log.event_type
            for log in ActivityLog.query.all()
        }

        assert 'entry_created' in event_types
        assert 'goal_created' in all_event_types
        assert 'budget_created' in all_event_types
        assert 'import_completed' in all_event_types
        assert 'export_csv' in all_event_types


def test_profile_hub_shows_session_labels_and_system_status_details(client, app):
    with app.app_context():
        user = User(username='auditprofile', email='auditprofile@example.com', name='Audit Profile')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        db.session.add(
            UserSession(
                user_id=user.id,
                session_token_hash='historic-session',
                ip_address='127.0.0.1',
                user_agent='Mozilla/5.0 Chrome/123.0',
                started_at=datetime(2026, 3, 15, 10, 0),
                last_seen_at=datetime(2026, 3, 15, 10, 5),
                ended_at=datetime(2026, 3, 15, 10, 6),
                ended_reason='timeout',
                is_current=False,
            )
        )
        db.session.add(
            ActivityLog(
                user_id=user.id,
                event_category='entries',
                event_type='entry_created',
                message='Lançamento criado com sucesso.',
                details_json='{"category":"Trabalho","payment_method":"Transferência / PIX"}',
            )
        )
        db.session.add(
            SystemEvent(
                user_id=user.id,
                severity='error',
                source='imports',
                event_code='import_unexpected_failed',
                message='Erro inesperado durante importação de arquivo.',
                details_json='{"error":"disk full"}',
            )
        )
        db.session.commit()

    _login(client, 'auditprofile')
    response = client.get('/profile')

    assert response.status_code == 200
    assert b'Banco de dados' in response.data
    assert b'Agendador de backups' in response.data
    assert b'Manifesto de atualiza' in response.data
    assert b'Encerrada por inatividade' in response.data
    assert b'Google Chrome' in response.data
    assert b'Forma de pagamento/recebimento' in response.data
    assert b'Lan\xc3\xa7amentos' in response.data
    assert b'disk full' in response.data


def test_profile_bootstraps_active_session_for_authenticated_user_without_audit_token(client, app):
    with app.app_context():
        user = User(username='sessionbootstrap', email='sessionbootstrap@example.com', name='Session Bootstrap')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with client.session_transaction() as flask_session:
        flask_session['_user_id'] = str(user_id)
        flask_session['_fresh'] = True

    response = client.get('/profile')

    assert response.status_code == 200

    with app.app_context():
        assert UserSession.query.filter_by(user_id=user_id, is_current=True).count() == 1


def test_profile_bootstrap_reconciles_duplicate_active_sessions_for_same_client(client, app):
    user_agent = 'pytest-agent'

    with app.app_context():
        user = User(username='sessionreconcile', email='sessionreconcile@example.com', name='Session Reconcile')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        db.session.add(
            UserSession(
                user_id=user_id,
                session_token_hash='legacy-session',
                ip_address='127.0.0.1',
                user_agent=user_agent,
                started_at=datetime(2026, 3, 16, 10, 0),
                last_seen_at=datetime(2026, 3, 16, 10, 1),
                is_current=True,
            )
        )
        db.session.commit()
        existing_session_id = (
            UserSession.query.filter_by(user_id=user_id, is_current=True).first().id
        )

    with client.session_transaction() as flask_session:
        flask_session['_user_id'] = str(user_id)
        flask_session['_fresh'] = True

    response = client.get('/profile', headers={'User-Agent': user_agent})

    assert response.status_code == 200

    with app.app_context():
        active_sessions = UserSession.query.filter_by(user_id=user_id, is_current=True).all()
        assert len(active_sessions) == 1
        assert active_sessions[0].id == existing_session_id


def test_profile_hub_paginates_backup_and_activity_history(client, app):
    app.config['PROFILE_BACKUPS_PAGE_SIZE'] = 2
    app.config['PROFILE_ACTIVITIES_PAGE_SIZE'] = 2

    with app.app_context():
        user = User(username='paginationhub', email='paginationhub@example.com', name='Pagination Hub')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        for index in range(3):
            db.session.add(
                BackupRecord(
                    user_id=user.id,
                    file_name=f'backup-{index}.zip',
                    storage_path=f'C:/fake/backup-{index}.zip',
                    checksum=f'checksum-{index}',
                    trigger_source='Manual',
                    status='Concluido',
                    file_size_bytes=1024 + index,
                    created_at=datetime(2026, 3, 15, 10, index),
                )
            )
            db.session.add(
                ActivityLog(
                    user_id=user.id,
                    event_category='entries',
                    event_type=f'entry_event_{index}',
                    message=f'Atividade {index}',
                    created_at=datetime(2026, 3, 15, 11, index),
                )
            )
        db.session.commit()

    _login(client, 'paginationhub')

    first_page = client.get('/profile')
    second_page = client.get('/profile?backups_page=2&activities_page=2#activity-pane')

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert b'Total: 3' in first_page.data
    assert b'backup-2.zip' in first_page.data
    assert b'backup-0.zip' not in first_page.data
    assert b'backup-0.zip' in second_page.data
    assert b'Atividade 2' in first_page.data
    assert b'Atividade 0' not in first_page.data
    assert b'Atividade 0' in second_page.data
    assert b'backups_page=2' in first_page.data
    assert b'#backups-pane' in first_page.data
    assert b'activities_page=2' in first_page.data
    assert b'#activity-pane' in first_page.data

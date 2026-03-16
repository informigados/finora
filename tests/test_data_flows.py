import io
from datetime import datetime

from database.db import db
from models.finance import Finance
from models.user import User


def test_import_csv_persists_valid_rows_and_skips_invalid_ones(auth_client, app):
    csv_content = (
        "descricao,valor,categoria,tipo,status,data\n"
        "Mercado,150.50,Alimentação,Despesa,Pago,2026-03-10\n"
        "Linha inválida,0,Lazer,Despesa,Pendente,2026-03-11\n"
    )

    response = auth_client.post(
        '/import',
        data={'file': (io.BytesIO(csv_content.encode('utf-8')), 'finances.csv')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'importado(s) com sucesso' in response.data
    assert b'linha(s) foram ignoradas por inconsist' in response.data

    with app.app_context():
        entries = Finance.query.filter_by(description='Mercado').all()
        assert len(entries) == 1
        assert entries[0].user.username == 'testuser'


def test_export_csv_is_scoped_to_authenticated_user(auth_client, app):
    with app.app_context():
        owner = User.query.filter_by(username='testuser').first()
        other_user = User(username='otheruser', email='other@example.com', name='Other User')
        other_user.set_password('Password123')
        db.session.add(other_user)
        db.session.commit()

        db.session.add_all([
            Finance(
                description='Owner Salary',
                value=3200.0,
                category='Salário',
                type='Receita',
                status='Pago',
                due_date=datetime(2026, 3, 5).date(),
                payment_method='Transferência / PIX',
                user_id=owner.id,
            ),
            Finance(
                description='Other Salary',
                value=4800.0,
                category='Salário',
                type='Receita',
                status='Pago',
                due_date=datetime(2026, 3, 5).date(),
                user_id=other_user.id,
            ),
        ])
        db.session.commit()

    response = auth_client.get('/export/csv/2026/3')

    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert 'Owner Salary' in response.text
    assert 'Transferência / PIX' in response.text
    assert 'Other Salary' not in response.text


def test_backup_route_warns_for_in_memory_sqlite(auth_client):
    response = auth_client.get('/backup/download', follow_redirects=True)

    assert response.status_code == 200
    assert b'Banco de dados SQLite inv' in response.data

from flask import Blueprint, send_file, flash, redirect, current_app, url_for
from flask_login import login_required
from flask.typing import ResponseReturnValue
from flask_babel import gettext as _
from database.db import db
import tempfile
import sqlite3
import os
import zipfile
import io
from datetime import datetime

backup_bp = Blueprint('backup', __name__)

@backup_bp.route('/backup/download')
@login_required
def download_backup() -> ResponseReturnValue:
    try:
        engine_url = db.engine.url
        if not engine_url.drivername.startswith('sqlite'):
            flash(_('Backup por arquivo está disponível apenas para SQLite. Use backup nativo do seu banco atual.'), 'warning')
            return redirect(url_for('dashboard.index'))

        db_path = engine_url.database or ''
        if not db_path or db_path == ':memory:':
            flash(_('Banco de dados SQLite inválido para backup.'), 'error')
            return redirect(url_for('dashboard.index'))

        if not os.path.isabs(db_path):
            instance_candidate = os.path.join(current_app.instance_path, db_path)
            root_candidate = os.path.join(current_app.root_path, db_path)
            db_path = instance_candidate if os.path.exists(instance_candidate) else root_candidate

        if not os.path.exists(db_path):
            flash(_('Banco de dados não encontrado para backup.'), 'error')
            return redirect(url_for('dashboard.index'))

        memory_file = io.BytesIO()
        with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as snapshot_file:
            snapshot_path = snapshot_file.name

        try:
            source = sqlite3.connect(db_path)
            destination = sqlite3.connect(snapshot_path)
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()

            with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(snapshot_path, os.path.basename(db_path))
        finally:
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
            
        memory_file.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"finora_backup_{timestamp}.zip"
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        current_app.logger.exception('Erro ao gerar backup: %s', e)
        flash(_('Erro ao gerar backup. Tente novamente.'), 'error')
        return redirect(url_for('dashboard.index'))

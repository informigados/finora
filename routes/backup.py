from flask import Blueprint, send_file, flash, redirect, current_app, url_for
from flask_login import login_required
from flask_babel import gettext as _
import os
import zipfile
import io
from datetime import datetime

backup_bp = Blueprint('backup', __name__)

@backup_bp.route('/backup/download')
@login_required
def download_backup():
    try:
        db_path = os.path.join(current_app.root_path, 'database', 'finora.db')
        if not os.path.exists(db_path):
            flash(_('Banco de dados não encontrado para backup.'), 'error')
            return redirect(url_for('dashboard.index'))
            
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_path, 'finora.db')
            
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

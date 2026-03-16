from flask import Blueprint, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from flask.typing import ResponseReturnValue
from database.db import db
from flask_babel import gettext as _

from services.import_service import (
    ImportValidationError,
    import_finances_from_file,
)
from services.profile_service import record_activity, record_system_event

import_bp = Blueprint('import', __name__)

@import_bp.route('/import', methods=['POST'])
@login_required
def import_file() -> ResponseReturnValue:
    if 'file' not in request.files:
        flash(_('Nenhum arquivo foi enviado para importação.'), 'error')
        return redirect(url_for('dashboard.index'))
    
    file = request.files['file']
    if file.filename == '':
        flash(_('Selecione um arquivo antes de importar.'), 'error')
        return redirect(url_for('dashboard.index'))

    try:
        result = import_finances_from_file(
            uploaded_file=file,
            user_id=current_user.id,
            max_rows=current_app.config.get('MAX_IMPORT_ROWS', 20000),
            max_file_size=current_app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024),
        )

        if result.imported_rows == 0:
            flash(_('Nenhum lançamento válido foi encontrado no arquivo.'), 'warning')
            return redirect(url_for('dashboard.index'))

        db.session.add_all(result.entries)
        record_activity(
            current_user,
            'imports',
            'import_completed',
            'Importação concluída com sucesso.',
            details={
                'imported_rows': result.imported_rows,
                'skipped_rows': result.skipped_rows,
                'filename': file.filename,
            },
            ip_address=request.remote_addr,
            commit=False,
        )
        db.session.commit()
        flash(
            _('%(count)d lançamento(s) importado(s) com sucesso.', count=result.imported_rows),
            'success'
        )

        if result.skipped_rows > 0:
            preview = '; '.join(result.errors[:3])
            remainder = result.skipped_rows - 3
            suffix = ''
            if remainder > 0:
                suffix = _(' ... e mais %(count)d linha(s).', count=remainder)
            flash(
                _(
                    '%(count)d linha(s) foram ignoradas por inconsistência: %(preview)s%(suffix)s',
                    count=result.skipped_rows,
                    preview=preview,
                    suffix=suffix,
                ),
                'warning'
            )
    except ImportValidationError as exc:
        db.session.rollback()
        record_system_event(
            'warning',
            'imports',
            'Importação rejeitada por validação.',
            user=current_user,
            event_code='import_validation_failed',
            details={'filename': file.filename, 'error': str(exc)},
        )
        flash(str(exc), 'error')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Erro inesperado durante importação de arquivo.')
        record_system_event(
            'error',
            'imports',
            'Erro inesperado durante importação de arquivo.',
            user=current_user,
            event_code='import_unexpected_failed',
            details={'filename': file.filename},
        )
        flash(_('Erro inesperado ao importar arquivo. Nenhuma alteração foi salva.'), 'error')

    return redirect(url_for('dashboard.index'))

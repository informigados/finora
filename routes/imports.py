from flask import Blueprint, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from database.db import db
from flask_babel import gettext as _

from services.import_service import (
    ImportValidationError,
    import_finances_from_file,
)

import_bp = Blueprint('import', __name__)

@import_bp.route('/import', methods=['POST'])
@login_required
def import_file():
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

        db.session.bulk_save_objects(result.entries)
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
        flash(str(exc), 'error')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Erro inesperado durante importação de arquivo.')
        flash(_('Erro inesperado ao importar arquivo. Nenhuma alteração foi salva.'), 'error')

    return redirect(url_for('dashboard.index'))

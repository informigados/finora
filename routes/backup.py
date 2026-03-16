import os

from flask import Blueprint, current_app, flash, redirect, request, send_file, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required
from flask.typing import ResponseReturnValue

from models.backup import BackupRecord
from services.backup_service import (
    apply_backup_schedule_update,
    create_backup_for_user,
    delete_backup_record,
)

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/backup/download')
@login_required
def download_backup() -> ResponseReturnValue:
    try:
        backup_record = create_backup_for_user(
            current_user._get_current_object(),
            current_app,
            trigger_source='Manual',
        )
        return send_file(
            backup_record.storage_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=backup_record.file_name,
        )
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('auth.profile', _anchor='backups-pane'))
    except Exception as exc:
        current_app.logger.exception('Erro ao gerar backup: %s', exc)
        flash(_('Erro ao gerar backup. Tente novamente.'), 'error')
        return redirect(url_for('auth.profile', _anchor='backups-pane'))


@backup_bp.route('/backup/history/<int:record_id>/download')
@login_required
def download_saved_backup(record_id) -> ResponseReturnValue:
    backup_record = BackupRecord.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    if not os.path.exists(backup_record.storage_path):
        flash(_('O arquivo de backup não está mais disponível para download.'), 'warning')
        return redirect(url_for('auth.profile', _anchor='backups-pane'))

    return send_file(
        backup_record.storage_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name=backup_record.file_name,
    )


@backup_bp.route('/backup/history/<int:record_id>/delete', methods=['POST'])
@login_required
def delete_saved_backup(record_id) -> ResponseReturnValue:
    backup_record = BackupRecord.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    error_code = delete_backup_record(current_user._get_current_object(), backup_record)
    if error_code:
        flash(_('Não foi possível remover o backup selecionado.'), 'error')
        return redirect(url_for('auth.profile', _anchor='backups-pane'))

    flash(_('Backup removido com sucesso!'), 'success')
    return redirect(url_for('auth.profile', _anchor='backups-pane'))


@backup_bp.route('/backup/schedule', methods=['POST'])
@login_required
def update_backup_schedule() -> ResponseReturnValue:
    error_code = apply_backup_schedule_update(
        current_user._get_current_object(),
        form=request.form,
        default_retention_count=current_app.config.get('BACKUP_DEFAULT_RETENTION_COUNT', 20),
    )
    if error_code:
        error_messages = {
            'invalid_schedule_value': _('Os valores informados para a rotina de backup são inválidos.'),
            'invalid_frequency': _('Frequência de backup inválida.'),
            'invalid_times_per_period': _('Quantidade de execuções por período inválida.'),
            'invalid_run_hour': _('Hora inicial inválida para a rotina de backup.'),
            'invalid_run_minute': _('Minuto inválido para a rotina de backup.'),
            'invalid_retention_count': _('Retenção máxima inválida para backups.'),
            'invalid_day_of_week': _('Dia da semana inválido para a rotina semanal.'),
            'invalid_day_of_month': _('Dia do mês inválido para a rotina mensal.'),
            'backup_schedule_persist_failed': _('Não foi possível salvar a rotina de backup.'),
        }
        flash(
            error_messages.get(
                error_code,
                _('Não foi possível atualizar a rotina de backup. Revise os dados informados.'),
            ),
            'error',
        )
        return redirect(url_for('auth.profile', _anchor='backups-pane'))

    flash(_('Rotina de backup atualizada com sucesso!'), 'success')
    return redirect(url_for('auth.profile', _anchor='backups-pane'))

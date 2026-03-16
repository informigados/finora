from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required
from flask.typing import ResponseReturnValue

from services.update_service import apply_update, get_update_overview, check_for_updates

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def welcome() -> ResponseReturnValue:
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return render_template('welcome.html')


@public_bp.route('/about')
def about() -> ResponseReturnValue:
    return render_template('about.html', **get_update_overview(current_app))


@public_bp.route('/about/check-update', methods=['POST'])
def about_check_update() -> ResponseReturnValue:
    result = check_for_updates(current_app)
    if result.get('error'):
        error_message = (
            _(
                'Não foi possível verificar atualizações: %(error)s',
                error=result['error'],
            )
            if current_user.is_authenticated
            else _('Não foi possível verificar atualizações no momento. Faça login para ver os detalhes.')
        )
        flash(
            error_message,
            'error',
        )
        return redirect(url_for('public.about'))

    if result.get('update_available'):
        flash(
            _(
                'Nova versão disponível: %(version)s. Revise os detalhes e escolha quando atualizar.',
                version=result['manifest']['version'],
            ),
            'info',
        )
    else:
        flash(_('Esta instalação já está atualizada.'), 'success')
    return redirect(url_for('public.about'))


@public_bp.route('/about/apply-update', methods=['POST'])
@login_required
def about_apply_update() -> ResponseReturnValue:
    try:
        result = apply_update(current_app, user=current_user._get_current_object())
    except Exception as exc:
        flash(
            _('Não foi possível aplicar a atualização: %(error)s', error=str(exc)),
            'error',
        )
        return redirect(url_for('public.about'))

    if not result.get('applied'):
        flash(_('Nenhuma atualização aplicável foi encontrada no momento.'), 'warning')
        return redirect(url_for('public.about'))

    flash(
        _(
            'Atualização aplicada com sucesso. Versão instalada: %(version)s. Reinicie o Finora para carregar todos os componentes atualizados.',
            version=result['manifest']['version'],
        ),
        'success',
    )
    return redirect(url_for('public.about'))


@public_bp.route('/sobre')
def about_legacy() -> ResponseReturnValue:
    return redirect(url_for('public.about'), code=301)

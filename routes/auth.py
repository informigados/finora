import time

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue
from flask_babel import gettext as _
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from config import DEFAULT_APP_VERSION
from database.db import db
from extensions import limiter
from models.time_utils import utcnow_naive
from models.user import User
from services.auth_service import (
    MIN_PASSWORD_LENGTH,
    commit_auth_security_state,
    consume_reset_password_token,
    find_user_by_identifier,
    generate_recovery_key,
    is_strong_password,
    is_valid_email,
    perform_signup_lookup_delay,
    resolve_user_from_reset_token,
    send_recovery_key_email,
    send_reset_password_email,
)
from services.backup_service import (
    BACKUP_FREQUENCY_OPTIONS,
    BACKUP_TIMES_PER_PERIOD_OPTIONS,
    BACKUP_WEEKDAY_OPTIONS,
    get_or_create_backup_schedule,
)
from services.profile_service import (
    DELETE_CONFIRMATION_TOKEN,
    VALID_SESSION_TIMEOUT_OPTIONS,
    apply_profile_update,
    end_user_session,
    get_profile_hub_context,
    record_activity,
    record_system_event,
    change_user_password,
    delete_user_account,
    start_user_session,
)

auth_bp = Blueprint('auth', __name__)

def _generic_recovery_notice() -> str:
    return _(
        'Se existir uma conta correspondente, as instruções de recuperação foram processadas. '
        'Use o método escolhido para concluir a redefinição de senha.'
    )


def _lockout_notice() -> str:
    return _(
        'Muitas tentativas de acesso foram detectadas. Aguarde alguns minutos antes de tentar novamente.'
    )


@auth_bp.route('/check_username', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('AUTH_RATE_LIMIT_LOOKUPS', '30 per minute'), methods=['POST'])
def check_username() -> ResponseReturnValue:
    started_at = time.perf_counter()
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({'available': False, 'error': _('Nome de usuário inválido.')}), 400

    User.query.filter_by(username=username).first()
    perform_signup_lookup_delay(started_at)
    return jsonify(
        {
            'available': True,
            'verified': False,
            'message': _(
                'A disponibilidade definitiva será confirmada ao concluir o cadastro.'
            ),
        }
    )


@auth_bp.route('/check_email', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('AUTH_RATE_LIMIT_LOOKUPS', '30 per minute'), methods=['POST'])
def check_email() -> ResponseReturnValue:
    started_at = time.perf_counter()
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email or not is_valid_email(email):
        return jsonify({'available': False, 'error': _('E-mail inválido.')}), 400

    User.query.filter_by(email=email).first()
    perform_signup_lookup_delay(started_at)
    return jsonify(
        {
            'available': True,
            'verified': False,
            'message': _(
                'A disponibilidade definitiva será confirmada ao concluir o cadastro.'
            ),
        }
    )


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config.get('AUTH_RATE_LIMIT_LOGIN', '10 per 5 minutes'), methods=['POST'])
def login() -> ResponseReturnValue:
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        identifier = (request.form.get('identifier') or '').strip()
        password = request.form.get('password') or ''
        remember = bool(request.form.get('remember'))
        now = utcnow_naive()

        if not identifier or not password:
            flash(_('Informe usuário/e-mail e senha para continuar.'), 'error')
            return redirect(url_for('auth.login'))

        user = find_user_by_identifier(identifier)

        if user and user.locked_until and user.locked_until <= now:
            user.reset_failed_logins()
            commit_auth_security_state()

        if user and user.is_locked_out(now):
            flash(_lockout_notice(), 'error')
            return redirect(url_for('auth.login'))

        if not user or not user.check_password(password):
            if user:
                user.register_failed_login(
                    max_attempts=current_app.config.get('AUTH_MAX_FAILED_LOGINS', 5),
                    lockout_minutes=current_app.config.get('AUTH_LOCKOUT_MINUTES', 15),
                    now=now,
                )
                commit_auth_security_state()

                if user.is_locked_out(now):
                    flash(_lockout_notice(), 'error')
                    return redirect(url_for('auth.login'))

            flash(_('Por favor verifique seus dados de login e tente novamente.'), 'error')
            return redirect(url_for('auth.login'))

        if user.failed_login_attempts or user.locked_until:
            user.reset_failed_logins()
            commit_auth_security_state()

        login_user(user, remember=remember)
        session['last_activity_ts'] = int(time.time())
        start_user_session(user, request, session)
        record_activity(
            user,
            'auth',
            'login_success',
            'Login realizado com sucesso.',
            details={'remember': remember},
            ip_address=request.remote_addr,
        )
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config.get('AUTH_RATE_LIMIT_REGISTER', '5 per hour'), methods=['POST'])
def register() -> ResponseReturnValue:
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        username = (request.form.get('username') or '').strip()
        name = (request.form.get('name') or '').strip()
        password = request.form.get('password') or ''

        if not is_valid_email(email):
            flash(_('Por favor, insira um endereço de e-mail válido.'), 'error')
            return redirect(url_for('auth.register'))

        if len(username) < 3:
            flash(_('Nome de usuário deve ter pelo menos 3 caracteres.'), 'error')
            return redirect(url_for('auth.register'))

        if not is_strong_password(password):
            flash(
                _(
                    'A senha deve ter ao menos %(length)d caracteres, incluindo letras maiúsculas, minúsculas e números.',
                    length=MIN_PASSWORD_LENGTH,
                ),
                'error',
            )
            return redirect(url_for('auth.register'))

        user = User.query.filter((User.email == email) | (User.username == username)).first()
        if user:
            flash(_('Endereço de e-mail ou nome de usuário já existe.'), 'error')
            return redirect(url_for('auth.register'))

        new_user = User(email=email, username=username, name=name)
        new_user.set_password(password)
        recovery_key = generate_recovery_key()
        new_user.set_recovery_key(recovery_key)

        try:
            db.session.add(new_user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(_('Não foi possível concluir o cadastro. Verifique os dados informados.'), 'error')
            return redirect(url_for('auth.register'))

        flash(
            _(
                'Conta criada com sucesso! Sua chave de recuperação é: %(key)s. Guarde-a em local seguro!',
                key=recovery_key,
            ),
            'success',
        )
        recovery_delivery = send_recovery_key_email(new_user, recovery_key, 'register')
        record_activity(
            new_user,
            'auth',
            'account_created',
            'Conta criada com sucesso.',
            details={
                'recovery_key_version': new_user.recovery_key_version,
                'delivery': recovery_delivery.get('delivery', 'none'),
            },
            ip_address=request.remote_addr,
        )
        if recovery_delivery.get('ok'):
            flash(_('Também enviamos a chave de recuperação para o seu e-mail.'), 'info')
        else:
            flash(_('O envio por e-mail da chave de recuperação não pôde ser concluído neste momento.'), 'warning')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout() -> ResponseReturnValue:
    user = current_user._get_current_object()
    record_activity(
        user,
        'auth',
        'logout',
        'Logout realizado pelo usuario.',
        ip_address=request.remote_addr,
    )
    end_user_session(user, session, 'logout')
    logout_user()
    response = redirect(url_for('auth.login'))
    remember_cookie_name = current_app.config.get('REMEMBER_COOKIE_NAME', 'remember_token')
    response.delete_cookie(remember_cookie_name)
    return response


@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config.get('AUTH_RATE_LIMIT_FORGOT_PASSWORD', '10 per hour'), methods=['POST'])
def forgot_password() -> ResponseReturnValue:
    if request.method == 'POST':
        identifier = (request.form.get('identifier') or '').strip()
        method = request.form.get('method')

        if method not in {'email', 'offline'}:
            flash(_('Método de recuperação inválido.'), 'error')
            return redirect(url_for('auth.forgot_password'))

        user = find_user_by_identifier(identifier)

        if method == 'email':
            if user:
                send_reset_password_email(user)

            flash(_generic_recovery_notice(), 'info')
            return redirect(url_for('auth.login'))

        flash(_generic_recovery_notice(), 'info')
        return redirect(url_for('auth.reset_password_offline', identifier=identifier))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset_password/offline', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config.get('AUTH_RATE_LIMIT_FORGOT_PASSWORD', '10 per hour'), methods=['POST'])
def reset_password_offline() -> ResponseReturnValue:
    identifier = (request.values.get('identifier') or '').strip()
    if request.method == 'POST':
        identifier = (request.form.get('identifier') or '').strip()
        key = (request.form.get('recovery_key') or '').strip().upper()
        new_password = request.form.get('new_password') or ''
        user = find_user_by_identifier(identifier)

        if not is_strong_password(new_password):
            flash(
                _(
                    'A nova senha deve ter ao menos %(length)d caracteres, incluindo letras maiúsculas, minúsculas e números.',
                    length=MIN_PASSWORD_LENGTH,
                ),
                'error',
            )
            return redirect(url_for('auth.reset_password_offline', identifier=identifier))

        if user and user.check_recovery_key(key):
            user.set_password(new_password)
            user.reset_failed_logins()
            user.bump_password_reset_version()
            try:
                db.session.commit()
                flash(_('Sua senha foi atualizada com sucesso!'), 'success')
                return redirect(url_for('auth.login'))
            except Exception:
                db.session.rollback()
                flash(_('Não foi possível atualizar a senha. Tente novamente.'), 'error')
                return redirect(url_for('auth.reset_password_offline', identifier=identifier))

        flash(_('Dados de recuperação inválidos. Verifique as informações e tente novamente.'), 'error')

    return render_template('auth/reset_password_offline.html', identifier=identifier)


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token: str) -> ResponseReturnValue:
    user, token_error = resolve_user_from_reset_token(token)
    if token_error == 'expired':  # nosec B105
        flash(_('Este link de recuperação expirou. Solicite um novo link.'), 'error')
        return redirect(url_for('auth.forgot_password'))
    if token_error == 'invalid' or not user:  # nosec B105
        flash(_('Link de recuperação inválido.'), 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password') or ''

        if not is_strong_password(new_password):
            flash(
                _(
                    'A nova senha deve ter ao menos %(length)d caracteres, incluindo letras maiúsculas, minúsculas e números.',
                    length=MIN_PASSWORD_LENGTH,
                ),
                'error',
            )
            return redirect(url_for('auth.reset_password_token', token=token))

        user.set_password(new_password)
        consume_reset_password_token(user, token)
        user.reset_failed_logins()
        user.bump_password_reset_version()
        try:
            db.session.commit()
            flash(_('Sua senha foi atualizada com sucesso!'), 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            db.session.rollback()
            flash(_('Não foi possível atualizar a senha. Tente novamente.'), 'error')

    return render_template('auth/reset_password_token.html', token=token, user=user)


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile() -> ResponseReturnValue:
    if request.method == 'POST':
        action = request.form.get('action') or ''

        if action == 'update_info':
            error_code = apply_profile_update(
                user=current_user,
                form=request.form,
                files=request.files,
                root_path=current_app.root_path,
                max_image_size=current_app.config.get('MAX_PROFILE_IMAGE_SIZE', 2 * 1024 * 1024),
            )

            if error_code == 'invalid_session_timeout':
                flash(_('Tempo de sessão inválido.'), 'error')
                return redirect(url_for('auth.profile'))
            if error_code == 'invalid_email':
                flash(_('Por favor, insira um endereço de e-mail válido.'), 'error')
                return redirect(url_for('auth.profile'))
            if error_code == 'duplicate_email':
                flash(_('Este endereço de e-mail já está em uso.'), 'error')
                return redirect(url_for('auth.profile'))
            if error_code == 'image_too_large':
                flash(_('A imagem excede o tamanho máximo permitido de 2 MB.'), 'error')
                return redirect(url_for('auth.profile'))
            if error_code == 'invalid_image_name':
                flash(_('Nome de arquivo inválido para upload de imagem.'), 'error')
                return redirect(url_for('auth.profile'))
            if error_code == 'invalid_image':
                flash(_('Arquivo de imagem inválido. Formatos permitidos: JPG, PNG e GIF.'), 'error')
                return redirect(url_for('auth.profile'))
            if error_code == 'profile_persist_failed':
                record_system_event(
                    'error',
                    'profile',
                    'Falha ao persistir atualizacao de perfil.',
                    user=current_user,
                    event_code='profile_persist_failed',
                )
                flash(_('Não foi possível atualizar o perfil. Revise os dados e tente novamente.'), 'error')
                return redirect(url_for('auth.profile'))

            if current_user.session_timeout_minutes > 0:
                session['last_activity_ts'] = int(time.time())
            else:
                session.pop('last_activity_ts', None)
            record_activity(
                current_user,
                'profile',
                'profile_updated',
                'Perfil atualizado com sucesso.',
                details={'session_timeout_minutes': current_user.session_timeout_minutes},
                ip_address=request.remote_addr,
            )
            flash(_('Perfil atualizado com sucesso!'), 'success')

        elif action == 'change_password':
            error_code = change_user_password(
                user=current_user,
                current_password=request.form.get('current_password') or '',
                new_password=request.form.get('new_password') or '',
            )
            if error_code == 'invalid_current_password':
                flash(_('Senha atual incorreta.'), 'error')
            elif error_code == 'weak_password':
                flash(
                    _(
                        'A nova senha deve ter ao menos %(length)d caracteres, incluindo letras maiúsculas, minúsculas e números.',
                        length=MIN_PASSWORD_LENGTH,
                    ),
                    'error',
                )
            elif error_code == 'password_update_failed':
                record_system_event(
                    'error',
                    'profile',
                    'Falha ao atualizar a senha do usuario.',
                    user=current_user,
                    event_code='password_update_failed',
                )
                flash(_('Não foi possível alterar a senha. Tente novamente.'), 'error')
            else:
                record_activity(
                    current_user,
                    'profile',
                    'password_changed',
                    'Senha atualizada com sucesso.',
                    ip_address=request.remote_addr,
                )
                flash(_('Senha alterada com sucesso!'), 'success')

        elif action == 'delete_account':
            confirmation = (request.form.get('confirmation') or '').strip().upper()
            if confirmation == DELETE_CONFIRMATION_TOKEN:
                user = current_user._get_current_object()
                end_user_session(user, session, 'account_deleted')
                logout_user()
                error_code = delete_user_account(user, current_app.root_path)
                if not error_code:
                    flash(_('Sua conta foi excluída permanentemente.'), 'info')
                    return redirect(url_for('public.welcome'))
                record_system_event(
                    'error',
                    'profile',
                    'Falha ao excluir conta de usuario.',
                    user=user,
                    event_code='delete_account_failed',
                )
                flash(_('Não foi possível excluir a conta neste momento.'), 'error')
                return redirect(url_for('auth.profile'))

            flash(
                _(
                    'Confirmação incorreta para exclusão de conta. Digite %(token)s para confirmar.',
                    token=DELETE_CONFIRMATION_TOKEN,
                ),
                'error',
            )
        elif action == 'email_recovery_key':
            recovery_key = current_user.get_recovery_key()
            if not recovery_key:
                flash(_('Sua chave atual não está disponível para reenvio. Gere uma nova chave para continuar.'), 'warning')
                return redirect(url_for('auth.profile', _anchor='recovery-pane'))

            delivery = send_recovery_key_email(current_user, recovery_key, 'resend')
            if delivery.get('ok'):
                record_activity(
                    current_user,
                    'profile',
                    'recovery_key_emailed',
                    'Chave de recuperação reenviada por e-mail.',
                    details={'delivery': delivery.get('delivery', 'none')},
                    ip_address=request.remote_addr,
                )
                flash(_('Chave de recuperação enviada para o seu e-mail.'), 'success')
            else:
                record_system_event(
                    'error',
                    'profile',
                    'Falha ao reenviar chave de recuperação.',
                    user=current_user,
                    event_code='recovery_key_email_failed',
                )
                flash(_('Não foi possível enviar a chave de recuperação por e-mail.'), 'error')
            return redirect(url_for('auth.profile', _anchor='recovery-pane'))

        elif action == 'regenerate_recovery_key':
            recovery_key = generate_recovery_key()
            current_user.set_recovery_key(recovery_key)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                record_system_event(
                    'error',
                    'profile',
                    'Falha ao regenerar chave de recuperação.',
                    user=current_user,
                    event_code='recovery_key_regenerate_failed',
                )
                flash(_('Não foi possível gerar uma nova chave de recuperação.'), 'error')
                return redirect(url_for('auth.profile', _anchor='recovery-pane'))

            delivery = send_recovery_key_email(current_user, recovery_key, 'regenerate')
            record_activity(
                current_user,
                'profile',
                'recovery_key_regenerated',
                'Nova chave de recuperação gerada.',
                details={'delivery': delivery.get('delivery', 'none')},
                ip_address=request.remote_addr,
            )
            flash(
                _(
                    'Nova chave de recuperação gerada com sucesso: %(key)s',
                    key=recovery_key,
                ),
                'success',
            )
            if delivery.get('ok'):
                flash(_('A nova chave também foi enviada para o seu e-mail.'), 'info')
            else:
                flash(_('O envio por e-mail da nova chave não pôde ser concluído.'), 'warning')
            return redirect(url_for('auth.profile', _anchor='recovery-pane'))

    current_user_obj = current_user._get_current_object()
    if current_user_obj.rewrap_recovery_key():
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    get_or_create_backup_schedule(
        current_user_obj,
        current_app.config.get('BACKUP_DEFAULT_RETENTION_COUNT', 20),
    )
    pagination_params = {
        'backups_page': request.args.get('backups_page', 1),
        'sessions_page': request.args.get('sessions_page', 1),
        'activities_page': request.args.get('activities_page', 1),
        'events_page': request.args.get('events_page', 1),
    }
    page_sizes = {
        'backups': current_app.config.get('PROFILE_BACKUPS_PAGE_SIZE', 10),
        'sessions': current_app.config.get('PROFILE_SESSIONS_PAGE_SIZE', 10),
        'activities': current_app.config.get('PROFILE_ACTIVITIES_PAGE_SIZE', 15),
        'events': current_app.config.get('PROFILE_SYSTEM_EVENTS_PAGE_SIZE', 12),
    }
    profile_context = get_profile_hub_context(
        current_user_obj,
        current_app.config.get('APP_VERSION', DEFAULT_APP_VERSION),
        current_app.config.get('BACKUP_DEFAULT_RETENTION_COUNT', 20),
        pagination_params=pagination_params,
        page_sizes=page_sizes,
    )
    return render_template(
        'auth/profile.html',
        delete_confirmation_token=DELETE_CONFIRMATION_TOKEN,
        session_timeout_options=sorted(VALID_SESSION_TIMEOUT_OPTIONS),
        backup_frequency_options=BACKUP_FREQUENCY_OPTIONS,
        backup_times_per_period_options=BACKUP_TIMES_PER_PERIOD_OPTIONS,
        backup_weekday_options=BACKUP_WEEKDAY_OPTIONS,
        **profile_context,
    )


@auth_bp.route('/session/refresh', methods=['POST'])
def refresh_session() -> ResponseReturnValue:
    if not current_user.is_authenticated:
        return jsonify({'ok': False, 'expired': True}), 401

    timeout_minutes = int(getattr(current_user, 'session_timeout_minutes', 0) or 0)
    if timeout_minutes <= 0:
        return jsonify({'ok': True, 'open_session': True}), 200

    now_ts = int(time.time())
    expires_at = now_ts + timeout_minutes * 60
    session['last_activity_ts'] = now_ts
    session.modified = True

    return jsonify({'ok': True, 'expires_at': expires_at}), 200

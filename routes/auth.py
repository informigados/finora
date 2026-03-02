import os
import re
import time
import uuid

from PIL import Image
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from database.db import db
from models.user import User

auth_bp = Blueprint('auth', __name__)

MIN_PASSWORD_LENGTH = 8
DELETE_CONFIRMATION_TOKEN = 'EXCLUIR'
DEFAULT_PROFILE_IMAGE = 'default_profile.svg'
ALLOWED_IMAGE_FORMATS = {'png', 'jpeg', 'jpg', 'gif'}
VALID_SESSION_TIMEOUT_OPTIONS = {0, 1, 2, 3, 4, 5, 10, 15, 30, 60}


def is_valid_email(email):
    pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    return re.match(pattern, email) is not None


def is_strong_password(password):
    if len(password or '') < MIN_PASSWORD_LENGTH:
        return False
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    return has_upper and has_lower and has_digit


def is_valid_image(file_stream):
    try:
        current_pos = file_stream.tell()
        img = Image.open(file_stream)
        img.verify()
        image_format = (img.format or '').lower()
        file_stream.seek(current_pos)
        return image_format in ALLOWED_IMAGE_FORMATS
    except Exception:
        return False


def _uploaded_file_size(file_storage):
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    return size


def _remove_profile_image_if_custom(filename):
    if not filename or filename == DEFAULT_PROFILE_IMAGE:
        return

    image_path = os.path.join(current_app.root_path, 'static', 'profile_pics', filename)
    if os.path.exists(image_path):
        os.remove(image_path)


def _parse_session_timeout_minutes(raw_value):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError('session_timeout')

    if value not in VALID_SESSION_TIMEOUT_OPTIONS:
        raise ValueError('session_timeout')
    return value


@auth_bp.route('/check_username', methods=['POST'])
def check_username():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({'available': False, 'error': _('Nome de usuário inválido.')}), 400

    user = User.query.filter_by(username=username).first()
    return jsonify({'available': user is None})


@auth_bp.route('/check_email', methods=['POST'])
def check_email():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email or not is_valid_email(email):
        return jsonify({'available': False, 'error': _('E-mail inválido.')}), 400

    user = User.query.filter_by(email=email).first()
    return jsonify({'available': user is None})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        identifier = (request.form.get('identifier') or '').strip()
        password = request.form.get('password') or ''
        remember = bool(request.form.get('remember'))

        if not identifier or not password:
            flash(_('Informe usuário/e-mail e senha para continuar.'), 'error')
            return redirect(url_for('auth.login'))

        user = User.query.filter(
            (User.email == identifier.lower()) | (User.username == identifier)
        ).first()

        if not user or not user.check_password(password):
            flash(_('Por favor verifique seus dados de login e tente novamente.'), 'error')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        session['last_activity_ts'] = int(time.time())
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
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
        recovery_key = str(uuid.uuid4()).replace('-', '').upper()[:16]
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
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = (request.form.get('identifier') or '').strip()
        method = request.form.get('method')

        if method not in {'email', 'offline'}:
            flash(_('Método de recuperação inválido.'), 'error')
            return redirect(url_for('auth.forgot_password'))

        user = User.query.filter(
            (User.email == identifier.lower()) | (User.username == identifier)
        ).first()

        if not user:
            flash(_('Usuário não encontrado.'), 'error')
            return redirect(url_for('auth.forgot_password'))

        if method == 'email':
            flash(
                _(
                    'Um link de recuperação foi enviado para seu e-mail (Simulação: verifique o console).'
                ),
                'info',
            )
            current_app.logger.info(
                "Link de recuperação para %s: %s",
                user.email,
                url_for('auth.reset_password_token', token='dummy_token', _external=True),
            )
            return redirect(url_for('auth.login'))

        return redirect(url_for('auth.reset_password_offline', user_id=user.id))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset_password/offline/<int:user_id>', methods=['GET', 'POST'])
def reset_password_offline(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        key = (request.form.get('recovery_key') or '').strip()
        new_password = request.form.get('new_password') or ''

        if not is_strong_password(new_password):
            flash(
                _(
                    'A nova senha deve ter ao menos %(length)d caracteres, incluindo letras maiúsculas, minúsculas e números.',
                    length=MIN_PASSWORD_LENGTH,
                ),
                'error',
            )
            return redirect(url_for('auth.reset_password_offline', user_id=user.id))

        if user.check_recovery_key(key):
            user.set_password(new_password)
            try:
                db.session.commit()
                flash(_('Sua senha foi atualizada com sucesso!'), 'success')
                return redirect(url_for('auth.login'))
            except Exception:
                db.session.rollback()
                flash(_('Não foi possível atualizar a senha. Tente novamente.'), 'error')

        flash(_('Chave de recuperação inválida.'), 'error')

    return render_template('auth/reset_password_offline.html', user=user)


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    flash(_('Funcionalidade de token ainda não implementada (use a chave de recuperação).'), 'warning')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_info':
            current_user.name = (request.form.get('name') or '').strip() or None
            new_email = (request.form.get('email') or '').strip().lower()
            raw_timeout = request.form.get('session_timeout_minutes', '0')

            try:
                current_user.session_timeout_minutes = _parse_session_timeout_minutes(raw_timeout)
            except ValueError:
                flash(_('Tempo de sessão inválido.'), 'error')
                return redirect(url_for('auth.profile'))

            if new_email and new_email != current_user.email:
                if not is_valid_email(new_email):
                    flash(_('Por favor, insira um endereço de e-mail válido.'), 'error')
                    return redirect(url_for('auth.profile'))

                existing_user = User.query.filter(
                    User.email == new_email, User.id != current_user.id
                ).first()
                if existing_user:
                    flash(_('Este endereço de e-mail já está em uso.'), 'error')
                    return redirect(url_for('auth.profile'))

                current_user.email = new_email

            if 'delete_image' in request.form:
                old_image = current_user.profile_image
                current_user.profile_image = DEFAULT_PROFILE_IMAGE
                _remove_profile_image_if_custom(old_image)
            elif 'profile_image' in request.files:
                file = request.files['profile_image']
                if file and file.filename:
                    max_image_size = current_app.config.get('MAX_PROFILE_IMAGE_SIZE', 2 * 1024 * 1024)
                    if _uploaded_file_size(file) > max_image_size:
                        flash(_('A imagem excede o tamanho máximo permitido de 2 MB.'), 'error')
                        return redirect(url_for('auth.profile'))

                    if is_valid_image(file.stream):
                        safe_original_name = secure_filename(file.filename)
                        if not safe_original_name:
                            flash(_('Nome de arquivo inválido para upload de imagem.'), 'error')
                            return redirect(url_for('auth.profile'))
                        filename = f"user_{current_user.id}_{uuid.uuid4().hex[:8]}_{safe_original_name}"
                        filepath = os.path.join(current_app.root_path, 'static', 'profile_pics', filename)
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        file.save(filepath)

                        old_image = current_user.profile_image
                        current_user.profile_image = filename
                        _remove_profile_image_if_custom(old_image)
                    else:
                        flash(_('Arquivo de imagem inválido. Formatos permitidos: JPG, PNG e GIF.'), 'error')
                        return redirect(url_for('auth.profile'))

            try:
                db.session.commit()
                if current_user.session_timeout_minutes > 0:
                    session['last_activity_ts'] = int(time.time())
                else:
                    session.pop('last_activity_ts', None)
                flash(_('Perfil atualizado com sucesso!'), 'success')
            except IntegrityError:
                db.session.rollback()
                flash(_('Não foi possível atualizar o perfil. Revise os dados e tente novamente.'), 'error')

        elif action == 'change_password':
            current_password = request.form.get('current_password') or ''
            new_password = request.form.get('new_password') or ''

            if not current_user.check_password(current_password):
                flash(_('Senha atual incorreta.'), 'error')
            elif not is_strong_password(new_password):
                flash(
                    _(
                        'A nova senha deve ter ao menos %(length)d caracteres, incluindo letras maiúsculas, minúsculas e números.',
                        length=MIN_PASSWORD_LENGTH,
                    ),
                    'error',
                )
            else:
                current_user.set_password(new_password)
                try:
                    db.session.commit()
                    flash(_('Senha alterada com sucesso!'), 'success')
                except Exception:
                    db.session.rollback()
                    flash(_('Não foi possível alterar a senha. Tente novamente.'), 'error')

        elif action == 'delete_account':
            confirmation = (request.form.get('confirmation') or '').strip().upper()
            if confirmation == DELETE_CONFIRMATION_TOKEN:
                user = current_user
                _remove_profile_image_if_custom(user.profile_image)
                logout_user()
                db.session.delete(user)
                try:
                    db.session.commit()
                    flash(_('Sua conta foi excluída permanentemente.'), 'info')
                    return redirect(url_for('public.welcome'))
                except Exception:
                    db.session.rollback()
                    flash(_('Não foi possível excluir a conta neste momento.'), 'error')

            flash(
                _(
                    'Confirmação incorreta para exclusão de conta. Digite %(token)s para confirmar.',
                    token=DELETE_CONFIRMATION_TOKEN,
                ),
                'error',
            )

    return render_template(
        'auth/profile.html',
        delete_confirmation_token=DELETE_CONFIRMATION_TOKEN,
        session_timeout_options=sorted(VALID_SESSION_TIMEOUT_OPTIONS),
    )


@auth_bp.route('/session/refresh', methods=['POST'])
def refresh_session():
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

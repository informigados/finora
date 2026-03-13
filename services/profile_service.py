import os
import uuid

from PIL import Image
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from database.db import db
from models.user import User
from services.auth_service import is_strong_password, is_valid_email


DEFAULT_PROFILE_IMAGE = 'default_profile.svg'
ALLOWED_IMAGE_FORMATS = {'png', 'jpeg', 'jpg', 'gif'}
VALID_SESSION_TIMEOUT_OPTIONS = {0, 1, 2, 3, 4, 5, 10, 15, 30, 60}
DELETE_CONFIRMATION_TOKEN = 'EXCLUIR'  # nosec B105


def uploaded_file_size(file_storage):
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    return size


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


def remove_profile_image_if_custom(root_path, filename):
    if not filename or filename == DEFAULT_PROFILE_IMAGE:
        return

    image_path = os.path.join(root_path, 'static', 'profile_pics', filename)
    if os.path.exists(image_path):
        os.remove(image_path)


def parse_session_timeout_minutes(raw_value):
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError('session_timeout') from exc

    if value not in VALID_SESSION_TIMEOUT_OPTIONS:
        raise ValueError('session_timeout')
    return value


def apply_profile_update(user, form, files, root_path, max_image_size):
    user.name = (form.get('name') or '').strip() or None
    new_email = (form.get('email') or '').strip().lower()
    raw_timeout = form.get('session_timeout_minutes', '0')

    try:
        user.session_timeout_minutes = parse_session_timeout_minutes(raw_timeout)
    except ValueError:
        return 'invalid_session_timeout'

    if new_email and new_email != user.email:
        if not is_valid_email(new_email):
            return 'invalid_email'

        existing_user = User.query.filter(
            User.email == new_email, User.id != user.id
        ).first()
        if existing_user:
            return 'duplicate_email'

        user.email = new_email

    if 'delete_image' in form:
        old_image = user.profile_image
        user.profile_image = DEFAULT_PROFILE_IMAGE
        remove_profile_image_if_custom(root_path, old_image)
    elif 'profile_image' in files:
        file = files['profile_image']
        if file and file.filename:
            if uploaded_file_size(file) > max_image_size:
                return 'image_too_large'

            if not is_valid_image(file.stream):
                return 'invalid_image'

            safe_original_name = secure_filename(file.filename)
            if not safe_original_name:
                return 'invalid_image_name'

            filename = f"user_{user.id}_{uuid.uuid4().hex[:8]}_{safe_original_name}"
            filepath = os.path.join(root_path, 'static', 'profile_pics', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)

            old_image = user.profile_image
            user.profile_image = filename
            remove_profile_image_if_custom(root_path, old_image)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return 'profile_persist_failed'

    return None


def change_user_password(user, current_password, new_password):
    if not user.check_password(current_password):
        return 'invalid_current_password'
    if not is_strong_password(new_password):
        return 'weak_password'

    user.set_password(new_password)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 'password_update_failed'

    return None


def delete_user_account(user, root_path):
    remove_profile_image_if_custom(root_path, user.profile_image)
    db.session.delete(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 'delete_account_failed'

    return None

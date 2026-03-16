import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from database.db import db
from flask_login import UserMixin
from itsdangerous import BadSignature, URLSafeSerializer
from models.time_utils import utcnow_naive
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import timedelta

class User(UserMixin, db.Model):
    LEGACY_RECOVERY_KEY_SALT = b'finora-recovery-key-cipher'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    profile_image = db.Column(db.String(120), default='default_profile.svg')
    recovery_key_hash = db.Column(db.String(256))
    recovery_key_ciphertext = db.Column(db.Text)
    recovery_key_salt = db.Column(db.String(64))
    recovery_key_version = db.Column(db.Integer, nullable=False, default=1)
    password_reset_version = db.Column(db.Integer, nullable=False, default=0)
    password_reset_token_hash = db.Column(db.String(64))
    recovery_key_generated_at = db.Column(db.DateTime)
    recovery_key_last_sent_at = db.Column(db.DateTime)
    session_timeout_minutes = db.Column(db.Integer, nullable=False, default=0)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    
    # Relationships
    finances = db.relationship('Finance', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    goals = db.relationship('Goal', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    backup_schedule = db.relationship('BackupSchedule', backref='user', uselist=False, cascade="all, delete-orphan")
    backup_records = db.relationship('BackupRecord', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    login_sessions = db.relationship('UserSession', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    activity_logs = db.relationship('ActivityLog', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    system_events = db.relationship('SystemEvent', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def set_recovery_key(self, key):
        previous_version = int(self.recovery_key_version or 0)
        self.recovery_key_salt = self._generate_recovery_key_salt()
        self.recovery_key_hash = generate_password_hash(key)
        self.recovery_key_ciphertext = self._serialize_recovery_key(key, self.recovery_key_salt)
        self.recovery_key_version = previous_version + 1 if previous_version >= 1 else 1
        self.recovery_key_generated_at = utcnow_naive()
        self.recovery_key_last_sent_at = None

    def mark_recovery_key_sent(self):
        self.recovery_key_last_sent_at = utcnow_naive()
    
    def check_recovery_key(self, key):
        return check_password_hash(self.recovery_key_hash, key)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def bump_password_reset_version(self):
        self.password_reset_version = int(self.password_reset_version or 0) + 1

    def mark_reset_token_consumed(self, token_hash):
        self.password_reset_token_hash = token_hash

    @staticmethod
    def _build_recovery_key_serializer():
        from flask import current_app

        return URLSafeSerializer(
            current_app.config['SECRET_KEY'],
            salt='finora-recovery-key',
        )

    @staticmethod
    def _generate_recovery_key_salt():
        return base64.urlsafe_b64encode(os.urandom(16)).decode('ascii')

    @classmethod
    def _build_recovery_key_cipher(cls, salt_value=None):
        from flask import current_app

        secret_material = current_app.config['SECRET_KEY'].encode('utf-8')
        try:
            if salt_value:
                salt_bytes = base64.urlsafe_b64decode(salt_value.encode('ascii'))
            else:
                salt_bytes = cls.LEGACY_RECOVERY_KEY_SALT
        except Exception as exc:
            raise ValueError('Recovery key salt inválido.') from exc
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt_bytes,
            iterations=390000,
        )
        return Fernet(base64.urlsafe_b64encode(kdf.derive(secret_material)))

    @classmethod
    def _serialize_recovery_key(cls, key, salt_value=None):
        encrypted = cls._build_recovery_key_cipher(salt_value).encrypt(key.strip().upper().encode('utf-8'))
        return f'enc:{encrypted.decode("utf-8")}'

    @classmethod
    def _deserialize_recovery_key(cls, payload, salt_value=None):
        normalized_payload = (payload or '').strip()
        if not normalized_payload:
            return None

        if normalized_payload.startswith('enc:'):
            encrypted_payload = normalized_payload.split(':', 1)[1].encode('utf-8')
            decrypted_key = cls._build_recovery_key_cipher(salt_value).decrypt(encrypted_payload)
            return decrypted_key.decode('utf-8').strip().upper() or None

        data = cls._build_recovery_key_serializer().loads(normalized_payload)
        return (data.get('key') or '').strip().upper() or None

    def get_recovery_key(self):
        if not self.recovery_key_ciphertext:
            return None
        try:
            return self._deserialize_recovery_key(
                self.recovery_key_ciphertext,
                self.recovery_key_salt,
            )
        except (BadSignature, InvalidToken, ValueError, TypeError):
            return None

    def recovery_key_requires_rewrap(self):
        if not self.recovery_key_ciphertext:
            return False
        return (
            not self.recovery_key_ciphertext.strip().startswith('enc:')
            or not bool((self.recovery_key_salt or '').strip())
        )

    def rewrap_recovery_key(self):
        recovery_key = self.get_recovery_key()
        if not recovery_key:
            return False
        if not self.recovery_key_requires_rewrap():
            return False

        self.recovery_key_salt = self._generate_recovery_key_salt()
        self.recovery_key_ciphertext = self._serialize_recovery_key(
            recovery_key,
            self.recovery_key_salt,
        )
        return True

    def is_locked_out(self, now=None):
        current_time = now or utcnow_naive()
        return bool(self.locked_until and self.locked_until > current_time)

    def reset_failed_logins(self):
        self.failed_login_attempts = 0
        self.locked_until = None

    def register_failed_login(self, max_attempts, lockout_minutes, now=None):
        current_time = now or utcnow_naive()

        if self.locked_until and self.locked_until <= current_time:
            self.reset_failed_logins()

        self.failed_login_attempts = int(self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = current_time + timedelta(minutes=lockout_minutes)
            self.failed_login_attempts = 0

        return self.is_locked_out(current_time)

    def __repr__(self):
        return f'<User {self.username}>'

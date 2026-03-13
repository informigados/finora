from database.db import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import UTC, datetime, timedelta


def utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    profile_image = db.Column(db.String(120), default='default_profile.svg')
    recovery_key_hash = db.Column(db.String(256))
    session_timeout_minutes = db.Column(db.Integer, nullable=False, default=0)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    
    # Relationships
    finances = db.relationship('Finance', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    goals = db.relationship('Goal', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def set_recovery_key(self, key):
        self.recovery_key_hash = generate_password_hash(key)
    
    def check_recovery_key(self, key):
        return check_password_hash(self.recovery_key_hash, key)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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

from database.db import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    profile_image = db.Column(db.String(120), default='default_profile.svg')
    recovery_key_hash = db.Column(db.String(256))
    session_timeout_minutes = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
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

    def __repr__(self):
        return f'<User {self.username}>'

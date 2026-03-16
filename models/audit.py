from database.db import db
from models.time_utils import utcnow_naive


class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    __table_args__ = (
        db.Index('ix_user_sessions_user_started_at', 'user_id', 'started_at'),
        db.Index('ix_user_sessions_user_is_current', 'user_id', 'is_current'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_token_hash = db.Column(db.String(128), nullable=False, unique=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)
    ended_at = db.Column(db.DateTime, nullable=True)
    ended_reason = db.Column(db.String(40), nullable=True)
    is_current = db.Column(db.Boolean, nullable=False, default=True)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    __table_args__ = (
        db.Index('ix_activity_logs_user_created_at', 'user_id', 'created_at'),
        db.Index('ix_activity_logs_category_created_at', 'event_category', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    event_category = db.Column(db.String(40), nullable=False)
    event_type = db.Column(db.String(64), nullable=False)
    message = db.Column(db.Text, nullable=False)
    details_json = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)


class SystemEvent(db.Model):
    __tablename__ = 'system_events'
    __table_args__ = (
        db.Index('ix_system_events_severity_created_at', 'severity', 'created_at'),
        db.Index('ix_system_events_source_created_at', 'source', 'created_at'),
        db.Index('ix_system_events_user_created_at', 'user_id', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    severity = db.Column(db.String(20), nullable=False, default='info')
    source = db.Column(db.String(50), nullable=False)
    event_code = db.Column(db.String(80), nullable=True)
    message = db.Column(db.Text, nullable=False)
    details_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)
    resolved_at = db.Column(db.DateTime, nullable=True)

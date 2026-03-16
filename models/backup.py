from database.db import db
from models.time_utils import utcnow_naive


class BackupSchedule(db.Model):
    __tablename__ = 'backup_schedules'
    __table_args__ = (
        db.UniqueConstraint('user_id', name='uq_backup_schedule_user'),
        db.Index('ix_backup_schedule_enabled_next_run', 'enabled', 'next_run_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    frequency = db.Column(db.String(20), nullable=False, default='Semanal')
    times_per_period = db.Column(db.Integer, nullable=False, default=1)
    day_of_week = db.Column(db.Integer, nullable=True)
    day_of_month = db.Column(db.Integer, nullable=True)
    run_hour = db.Column(db.Integer, nullable=False, default=3)
    run_minute = db.Column(db.Integer, nullable=False, default=0)
    retention_count = db.Column(db.Integer, nullable=False, default=20)
    last_run_at = db.Column(db.DateTime, nullable=True)
    next_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class BackupRecord(db.Model):
    __tablename__ = 'backup_records'
    __table_args__ = (
        db.Index('ix_backup_records_user_created_at', 'user_id', 'created_at'),
        db.Index('ix_backup_records_schedule_created_at', 'schedule_id', 'created_at'),
        db.Index('ix_backup_records_status_created_at', 'status', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('backup_schedules.id'), nullable=True)
    trigger_source = db.Column(db.String(20), nullable=False, default='Manual')
    status = db.Column(db.String(20), nullable=False, default='Concluido')
    file_name = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(512), nullable=False)
    file_size_bytes = db.Column(db.BigInteger, nullable=True)
    checksum = db.Column(db.String(128), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    schedule = db.relationship('BackupSchedule', backref=db.backref('records', lazy='dynamic'))

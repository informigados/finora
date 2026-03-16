from database.db import db
from models.time_utils import utcnow_naive


class AppUpdateState(db.Model):
    __tablename__ = 'app_update_state'
    __table_args__ = (
        db.Index('ix_app_update_state_last_checked_at', 'last_checked_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    installed_version = db.Column(db.String(32), nullable=False)
    latest_known_version = db.Column(db.String(32), nullable=True)
    update_channel = db.Column(db.String(20), nullable=False, default='stable')
    status = db.Column(db.String(30), nullable=False, default='idle')
    last_checked_at = db.Column(db.DateTime, nullable=True)
    last_downloaded_at = db.Column(db.DateTime, nullable=True)
    downloaded_asset_path = db.Column(db.String(512), nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

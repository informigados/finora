from database.db import db
from datetime import datetime

class Goal(db.Model):
    __tablename__ = 'goals'
    __table_args__ = (
        db.Index('ix_goals_user_deadline', 'user_id', 'deadline'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    deadline = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'target_amount': self.target_amount,
            'current_amount': self.current_amount,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'progress': (self.current_amount / self.target_amount * 100) if self.target_amount > 0 else 0
        }

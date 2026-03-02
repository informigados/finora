from database.db import db
from datetime import datetime

class RecurringEntry(db.Model):
    __tablename__ = 'recurring_entries'
    __table_args__ = (
        db.Index('ix_recurring_user_next_run_active', 'user_id', 'next_run_date', 'active'),
    )

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'Receita', 'Despesa'
    frequency = db.Column(db.String(20), nullable=False) # 'Diário', 'Semanal', 'Mensal', 'Anual'
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    next_run_date = db.Column(db.Date, nullable=False)
    last_run_date = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'value': self.value,
            'category': self.category,
            'type': self.type,
            'frequency': self.frequency,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'next_run_date': self.next_run_date.isoformat() if self.next_run_date else None,
            'active': self.active
        }

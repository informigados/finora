from database.db import db
from datetime import datetime

class Finance(db.Model):
    __tablename__ = 'finances'
    __table_args__ = (
        db.Index('ix_finances_user_due_date', 'user_id', 'due_date'),
        db.Index('ix_finances_user_type_status', 'user_id', 'type', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'Receita', 'Despesa'
    status = db.Column(db.String(20), nullable=False, default='Pendente') # 'Pago', 'Pendente', 'Atrasado'
    due_date = db.Column(db.Date, nullable=False)
    payment_date = db.Column(db.Date, nullable=True)
    observations = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Nullable for migration, but should be filled
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'value': self.value,
            'category': self.category,
            'type': self.type,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'observations': self.observations
        }

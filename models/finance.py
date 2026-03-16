from database.db import db
from models.time_utils import utcnow_naive

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
    subcategory = db.Column(db.String(80), nullable=True)
    type = db.Column(db.String(20), nullable=False)  # 'Receita', 'Despesa'
    status = db.Column(db.String(20), nullable=False, default='Pendente') # 'Pago', 'Pendente', 'Atrasado'
    due_date = db.Column(db.Date, nullable=False)
    payment_date = db.Column(db.Date, nullable=True)
    payment_method = db.Column(db.String(40), nullable=True)
    observations = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'value': self.value,
            'category': self.category,
            'subcategory': self.subcategory,
            'type': self.type,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'payment_method': self.payment_method,
            'observations': self.observations
        }

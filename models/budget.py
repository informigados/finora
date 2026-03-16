from database.db import db
from models.time_utils import utcnow_naive

class Budget(db.Model):
    __tablename__ = 'budgets'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'category', 'period', name='uq_budget_user_category_period'),
        db.Index('ix_budgets_user_period', 'user_id', 'period'),
    )

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    limit_amount = db.Column(db.Float, nullable=False)
    period = db.Column(db.String(20), default='Mensal') # 'Mensal', 'Anual'
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'limit_amount': self.limit_amount,
            'period': self.period
        }

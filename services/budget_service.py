from database.db import db
from models.budget import Budget
from models.finance import Finance
from sqlalchemy import extract, func
from datetime import date

def get_budget_status(user_id, month=None, year=None):
    if not month or not year:
        today = date.today()
        month = today.month
        year = today.year
        
    budgets = Budget.query.filter_by(user_id=user_id).all()
    status_list = []

    if not budgets:
        return status_list

    monthly_categories = [b.category for b in budgets if b.period == 'Mensal']
    annual_categories = [b.category for b in budgets if b.period == 'Anual']

    monthly_spent = {}
    annual_spent = {}

    if monthly_categories:
        monthly_rows = db.session.query(
            Finance.category,
            func.sum(Finance.value).label('spent')
        ).filter(
            Finance.user_id == user_id,
            Finance.type == 'Despesa',
            Finance.category.in_(monthly_categories),
            extract('year', Finance.due_date) == year,
            extract('month', Finance.due_date) == month
        ).group_by(Finance.category).all()
        monthly_spent = {row.category: row.spent or 0.0 for row in monthly_rows}

    if annual_categories:
        annual_rows = db.session.query(
            Finance.category,
            func.sum(Finance.value).label('spent')
        ).filter(
            Finance.user_id == user_id,
            Finance.type == 'Despesa',
            Finance.category.in_(annual_categories),
            extract('year', Finance.due_date) == year
        ).group_by(Finance.category).all()
        annual_spent = {row.category: row.spent or 0.0 for row in annual_rows}

    for budget in budgets:
        if budget.period == 'Anual':
            spent = annual_spent.get(budget.category, 0.0)
        else:
            spent = monthly_spent.get(budget.category, 0.0)

        remaining = budget.limit_amount - spent
        percentage = (spent / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
        
        status_list.append({
            'budget': budget,
            'spent': spent,
            'remaining': remaining,
            'percentage': min(percentage, 100), # Cap for UI bar
            'raw_percentage': percentage,
            'display_percentage': round(percentage, 1),
            'over_budget': spent > budget.limit_amount
        })
        
    return status_list

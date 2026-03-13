from typing import Dict, Any, Optional
from sqlalchemy import func, extract, case
from models.finance import Finance
from database.db import db

def get_monthly_stats(month: int, year: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Calculates financial statistics for a specific month and year.
    Based on due_date. Optimized for a single aggregate query.
    """
    base_query = db.session.query(Finance).filter(
        extract('year', Finance.due_date) == year,
        extract('month', Finance.due_date) == month
    )
    
    if user_id:
        base_query = base_query.filter(Finance.user_id == user_id)
        
    # Single query aggregation for all totals
    stats = base_query.with_entities(
        func.sum(case((Finance.type == 'Despesa', Finance.value), else_=0)).label('total_despesa'),
        func.sum(case(((Finance.type == 'Despesa') & (Finance.status == 'Pago'), Finance.value), else_=0)).label('despesa_pago'),
        func.sum(case(((Finance.type == 'Despesa') & (Finance.status == 'Pendente'), Finance.value), else_=0)).label('despesa_pendente'),
        func.sum(case(((Finance.type == 'Despesa') & (Finance.status == 'Atrasado'), Finance.value), else_=0)).label('despesa_atrasado'),
        func.sum(case((Finance.type == 'Receita', Finance.value), else_=0)).label('total_receita')
    ).first()

    total_despesas_all = stats.total_despesa or 0.0
    total_despesa_pago = stats.despesa_pago or 0.0
    total_despesa_pendente = stats.despesa_pendente or 0.0
    total_despesa_atrasado = stats.despesa_atrasado or 0.0
    total_receita = stats.total_receita or 0.0
    
    balance = total_receita - total_despesas_all

    # Category Breakdown (Expenses only usually)
    categories = base_query.filter(Finance.type == 'Despesa')\
        .with_entities(Finance.category, func.sum(Finance.value))\
        .group_by(Finance.category).all()
    
    category_labels = [c[0] for c in categories]
    category_values = [c[1] for c in categories]

    return {
        'total_pago': total_despesa_pago,
        'total_pendente': total_despesa_pendente,
        'total_atrasado': total_despesa_atrasado,
        'total_geral': balance,
        'pendentes_atrasados': total_despesa_pendente + total_despesa_atrasado,
        'total_receitas': total_receita,
        'total_despesas': total_despesas_all,
        'chart_labels': category_labels,
        'chart_values': category_values
    }

def get_yearly_stats(year: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    if user_id is None:
        raise ValueError('user_id is required for yearly stats')

    monthly_rows = db.session.query(
        extract('month', Finance.due_date).label('month'),
        func.sum(case((Finance.type == 'Receita', Finance.value), else_=0)).label('receitas'),
        func.sum(case((Finance.type == 'Despesa', Finance.value), else_=0)).label('despesas'),
    ).filter(
        extract('year', Finance.due_date) == year,
        Finance.user_id == user_id,
    ).group_by(
        extract('month', Finance.due_date)
    ).order_by(
        extract('month', Finance.due_date)
    ).all()

    by_month = {}
    total_receitas = 0.0
    total_despesas = 0.0
    for row in monthly_rows:
        month = int(row.month)
        receitas = float(row.receitas or 0.0)
        despesas = float(row.despesas or 0.0)
        by_month[month] = {
            'receitas': receitas,
            'despesas': despesas,
            'saldo': receitas - despesas,
        }
        total_receitas += receitas
        total_despesas += despesas

    return {
        'year': year,
        'total_receitas': total_receitas,
        'total_despesas': total_despesas,
        'saldo': total_receitas - total_despesas,
        'by_month': by_month,
    }

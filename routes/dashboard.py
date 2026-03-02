from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from flask_babel import gettext as _
from datetime import date
from services.calculations import get_monthly_stats
from services.recurring_service import process_recurring_entries
from models.finance import Finance
from sqlalchemy import extract
from database.db import db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    today = date.today()
    return redirect(url_for('dashboard.view_month', year=today.year, month=today.month))

@dashboard_bp.route('/dashboard/<int:year>/<int:month>')
@login_required
def view_month(year, month):
    # Process recurring entries
    processed = process_recurring_entries(current_user.id)
    if processed > 0:
        flash(_('%(count)d lançamentos recorrentes foram gerados.', count=processed), 'info')

    stats = get_monthly_stats(month, year, user_id=current_user.id)
    
    # Translate chart labels
    stats['chart_labels'] = [_(label) for label in stats['chart_labels']]
    
    # Get entries for the month
    entries = db.session.query(Finance).filter(
        Finance.user_id == current_user.id,
        extract('year', Finance.due_date) == year,
        extract('month', Finance.due_date) == month
    ).order_by(Finance.due_date).all()
    
    return render_template('dashboard.html', 
                           year=year, 
                           month=month, 
                           stats=stats, 
                           entries=entries,
                           today=date.today())

@dashboard_bp.route('/dashboard/<int:year>')
@login_required
def view_year(year):
    monthly_data = []
    total_year_receita = 0
    total_year_despesa = 0
    
    month_names = [_('Jan'), _('Fev'), _('Mar'), _('Abr'), _('Mai'), _('Jun'), 
                   _('Jul'), _('Ago'), _('Set'), _('Out'), _('Nov'), _('Dez')]
    
    for m in range(1, 13):
        stats = get_monthly_stats(m, year, user_id=current_user.id)
        monthly_data.append({
            'month': m,
            'name': month_names[m-1],
            'receita': stats['total_receitas'],
            'despesa': stats['total_despesas'],
            'saldo': stats['total_geral']
        })
        total_year_receita += stats['total_receitas']
        total_year_despesa += stats['total_despesas']
        
    return render_template('year.html', 
                           year=year, 
                           monthly_data=monthly_data,
                           total_receita=total_year_receita,
                           total_despesa=total_year_despesa,
                           today=date.today())

@dashboard_bp.route('/dashboard/change_period', methods=['POST'])
@login_required
def change_period():
    month = request.form.get('month', type=int)
    year = request.form.get('year', type=int)
    if not year:
        return redirect(url_for('dashboard.index'))

    if month and (month < 1 or month > 12):
        flash(_('Mês inválido selecionado.'), 'error')
        return redirect(url_for('dashboard.index'))

    if not month:
        return redirect(url_for('dashboard.view_year', year=year))
    return redirect(url_for('dashboard.view_month', year=year, month=month))

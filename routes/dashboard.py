from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from flask.typing import ResponseReturnValue
from flask_babel import gettext as _
from datetime import date
from services.calculations import get_monthly_stats, get_yearly_stats
from models.finance import Finance
from sqlalchemy import extract
from database.db import db

dashboard_bp = Blueprint('dashboard', __name__)
DASHBOARD_ENTRIES_PER_PAGE = 50

@dashboard_bp.route('/dashboard')
@login_required
def index() -> ResponseReturnValue:
    today = date.today()
    return redirect(url_for('dashboard.view_month', year=today.year, month=today.month))

@dashboard_bp.route('/dashboard/<int:year>/<int:month>')
@login_required
def view_month(year: int, month: int) -> ResponseReturnValue:
    stats = get_monthly_stats(month, year, user_id=current_user.id)
    
    # Translate chart labels
    stats['chart_labels'] = [_(label) for label in stats['chart_labels']]
    
    page = request.args.get('page', default=1, type=int) or 1
    if page < 1:
        page = 1

    entries_query = db.session.query(Finance).filter(
        Finance.user_id == current_user.id,
        extract('year', Finance.due_date) == year,
        extract('month', Finance.due_date) == month
    ).order_by(Finance.due_date)

    entries_pagination = entries_query.paginate(
        page=page,
        per_page=DASHBOARD_ENTRIES_PER_PAGE,
        error_out=False,
    )
    if entries_pagination.pages > 0 and page > entries_pagination.pages:
        return redirect(
            url_for(
                'dashboard.view_month',
                year=year,
                month=month,
                page=entries_pagination.pages,
            )
        )

    entries = entries_pagination.items
    
    return render_template('dashboard.html', 
                           year=year, 
                           month=month, 
                           stats=stats, 
                           entries=entries,
                           entries_pagination=entries_pagination,
                           today=date.today())

@dashboard_bp.route('/dashboard/<int:year>')
@login_required
def view_year(year: int) -> ResponseReturnValue:
    yearly_stats = get_yearly_stats(year, user_id=current_user.id)
    monthly_data = []

    month_names = [_('Jan'), _('Fev'), _('Mar'), _('Abr'), _('Mai'), _('Jun'), 
                   _('Jul'), _('Ago'), _('Set'), _('Out'), _('Nov'), _('Dez')]

    for m in range(1, 13):
        month_stats = yearly_stats['by_month'].get(
            m,
            {'receitas': 0.0, 'despesas': 0.0, 'saldo': 0.0},
        )
        monthly_data.append({
            'month': m,
            'name': month_names[m-1],
            'receita': month_stats['receitas'],
            'despesa': month_stats['despesas'],
            'saldo': month_stats['saldo'],
        })

    return render_template('year.html', 
                           year=year, 
                           monthly_data=monthly_data,
                           total_receita=yearly_stats['total_receitas'],
                           total_despesa=yearly_stats['total_despesas'],
                           today=date.today())

@dashboard_bp.route('/dashboard/change_period', methods=['POST'])
@login_required
def change_period() -> ResponseReturnValue:
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

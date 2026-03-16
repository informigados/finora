from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask.typing import ResponseReturnValue
from flask_babel import gettext as _
from database.db import db
from models.budget import Budget
from services.catalogs import normalize_finance_category
from services.ownership import get_owned_or_none
from services.budget_service import get_budget_status
from services.profile_service import record_activity, record_system_event
from datetime import date

budgets_bp = Blueprint('budgets', __name__)
VALID_BUDGET_PERIODS = {'Mensal', 'Anual'}

@budgets_bp.route('/budgets')
@login_required
def index() -> ResponseReturnValue:
    today = date.today()
    month = request.args.get('month', today.month, type=int)
    year = request.args.get('year', today.year, type=int)
    
    budget_status = get_budget_status(current_user.id, month, year)
    
    return render_template('budgets.html', 
                           budget_status=budget_status, 
                           month=month, 
                           year=year,
                           today=today)

@budgets_bp.route('/budgets/add', methods=['POST'])
@login_required
def add_budget() -> ResponseReturnValue:
    data = request.form
    try:
        category = normalize_finance_category(data.get('category'), entry_type='Despesa')
        limit_amount = float(data['limit_amount'])
        if not category:
            flash(_('Categoria inválida. Selecione uma categoria permitida.'), 'error')
            return redirect(url_for('budgets.index'))
        if limit_amount <= 0:
            flash(_('O limite do orçamento deve ser maior que zero.'), 'error')
            return redirect(url_for('budgets.index'))
        if data.get('period') not in VALID_BUDGET_PERIODS:
            flash(_('Período de orçamento inválido.'), 'error')
            return redirect(url_for('budgets.index'))

        # Check if budget for category already exists
        existing = Budget.query.filter_by(
            user_id=current_user.id, 
            category=category,
            period=data['period']
        ).first()
        
        if existing:
            flash(_('Já existe um orçamento para esta categoria neste período.'), 'error')
        else:
            new_budget = Budget(
                category=category,
                limit_amount=limit_amount,
                period=data['period'],
                user_id=current_user.id
            )
            db.session.add(new_budget)
            record_activity(
                current_user,
                'budgets',
                'budget_created',
                'Orçamento definido com sucesso.',
                details={
                    'category': new_budget.category,
                    'period': new_budget.period,
                    'limit_amount': new_budget.limit_amount,
                },
                ip_address=request.remote_addr,
                commit=False,
            )
            db.session.commit()
            flash(_('Orçamento definido com sucesso!'), 'success')
             
    except Exception:
        db.session.rollback()
        record_system_event(
            'error',
            'budgets',
            'Falha ao definir orçamento.',
            user=current_user,
            event_code='budget_create_failed',
            details={'category': data.get('category') or ''},
        )
        flash(_('Erro ao definir orçamento.'), 'error')
         
    return redirect(url_for('budgets.index'))

@budgets_bp.route('/budgets/edit/<int:id>', methods=['POST'])
@login_required
def edit_budget(id: int) -> ResponseReturnValue:
    budget = get_owned_or_none(Budget, id, current_user.id)
    if budget:
        try:
            limit_amount = float(request.form['limit_amount'])
            if limit_amount <= 0:
                flash(_('O limite do orçamento deve ser maior que zero.'), 'error')
                return redirect(url_for('budgets.index'))
            if request.form.get('period') not in VALID_BUDGET_PERIODS:
                flash(_('Período de orçamento inválido.'), 'error')
                return redirect(url_for('budgets.index'))

            budget.limit_amount = limit_amount
            budget.period = request.form['period']
            record_activity(
                current_user,
                'budgets',
                'budget_updated',
                'Orçamento atualizado com sucesso.',
                details={
                    'category': budget.category,
                    'period': budget.period,
                    'limit_amount': budget.limit_amount,
                },
                ip_address=request.remote_addr,
                commit=False,
            )
            db.session.commit()
            flash(_('Orçamento atualizado!'), 'success')
        except Exception:
            db.session.rollback()
            record_system_event(
                'error',
                'budgets',
                'Falha ao atualizar orçamento.',
                user=current_user,
                event_code='budget_update_failed',
                details={'budget_id': id},
            )
            flash(_('Erro ao atualizar orçamento.'), 'error')
    return redirect(url_for('budgets.index'))

@budgets_bp.route('/budgets/delete/<int:id>', methods=['POST'])
@login_required
def delete_budget(id: int) -> ResponseReturnValue:
    budget = get_owned_or_none(Budget, id, current_user.id)
    if budget:
        budget_category = budget.category
        try:
            record_activity(
                current_user,
                'budgets',
                'budget_deleted',
                'Orçamento removido com sucesso.',
                details={'category': budget_category},
                ip_address=request.remote_addr,
                commit=False,
            )
            db.session.delete(budget)
            db.session.commit()
            flash(_('Orçamento removido!'), 'success')
        except Exception:
            db.session.rollback()
            record_system_event(
                'error',
                'budgets',
                'Falha ao remover orçamento.',
                user=current_user,
                event_code='budget_delete_failed',
                details={'budget_id': id},
            )
            flash(_('Erro ao remover orçamento.'), 'error')
    return redirect(url_for('budgets.index'))

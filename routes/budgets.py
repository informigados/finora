from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_babel import gettext as _
from database.db import db
from models.budget import Budget
from services.budget_service import get_budget_status
from datetime import date

budgets_bp = Blueprint('budgets', __name__)
VALID_BUDGET_PERIODS = {'Mensal', 'Anual'}

@budgets_bp.route('/budgets')
@login_required
def index():
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
def add_budget():
    data = request.form
    try:
        limit_amount = float(data['limit_amount'])
        if limit_amount <= 0:
            flash(_('O limite do orçamento deve ser maior que zero.'), 'error')
            return redirect(url_for('budgets.index'))
        if data.get('period') not in VALID_BUDGET_PERIODS:
            flash(_('Período de orçamento inválido.'), 'error')
            return redirect(url_for('budgets.index'))

        # Check if budget for category already exists
        existing = Budget.query.filter_by(
            user_id=current_user.id, 
            category=data['category'],
            period=data['period']
        ).first()
        
        if existing:
            flash(_('Já existe um orçamento para esta categoria neste período.'), 'error')
        else:
            new_budget = Budget(
                category=data['category'],
                limit_amount=limit_amount,
                period=data['period'],
                user_id=current_user.id
            )
            db.session.add(new_budget)
            db.session.commit()
            flash(_('Orçamento definido com sucesso!'), 'success')
             
    except Exception as e:
        db.session.rollback()
        flash(_('Erro ao definir orçamento.'), 'error')
         
    return redirect(url_for('budgets.index'))

@budgets_bp.route('/budgets/edit/<int:id>', methods=['POST'])
@login_required
def edit_budget(id):
    budget = db.session.get(Budget, id)
    if budget and budget.user_id == current_user.id:
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
            db.session.commit()
            flash(_('Orçamento atualizado!'), 'success')
        except Exception:
            db.session.rollback()
            flash(_('Erro ao atualizar orçamento.'), 'error')
    return redirect(url_for('budgets.index'))

@budgets_bp.route('/budgets/delete/<int:id>', methods=['POST'])
@login_required
def delete_budget(id):
    budget = db.session.get(Budget, id)
    if budget and budget.user_id == current_user.id:
        try:
            db.session.delete(budget)
            db.session.commit()
            flash(_('Orçamento removido!'), 'success')
        except Exception:
            db.session.rollback()
            flash(_('Erro ao remover orçamento.'), 'error')
    return redirect(url_for('budgets.index'))

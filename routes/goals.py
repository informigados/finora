from flask import Blueprint, request, redirect, url_for, render_template, flash
from flask_login import login_required, current_user
from flask_babel import gettext as _
from models.goal import Goal
from database.db import db
from datetime import datetime

goals_bp = Blueprint('goals', __name__)

@goals_bp.route('/goals')
@login_required
def index():
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    return render_template('goals.html', goals=goals)

@goals_bp.route('/goals/add', methods=['POST'])
@login_required
def add_goal():
    data = request.form
    name = (data.get('name') or '').strip()
    if not name:
        flash(_('Nome da meta é obrigatório.'), 'error')
        return redirect(url_for('goals.index'))

    try:
        target_amount = float(data['target_amount'])
        current_amount = float(data.get('current_amount', 0))
        if target_amount <= 0:
            raise ValueError('target_amount')
        if current_amount < 0:
            raise ValueError('current_amount')

        new_goal = Goal(
            name=name,
            target_amount=target_amount,
            current_amount=current_amount,
            deadline=datetime.strptime(data['deadline'], '%Y-%m-%d').date() if data.get('deadline') else None,
            user_id=current_user.id
        )
        db.session.add(new_goal)
        db.session.commit()
    except ValueError:
        db.session.rollback()
        flash(_('Os valores da meta devem ser válidos e maiores que zero.'), 'error')
        return redirect(url_for('goals.index'))
    except Exception:
        db.session.rollback()
        flash(_('Erro ao adicionar meta financeira.'), 'error')
        
    return redirect(url_for('goals.index'))

@goals_bp.route('/goals/delete/<int:id>', methods=['POST'])
@login_required
def delete_goal(id):
    goal = db.session.get(Goal, id)
    if goal and goal.user_id == current_user.id:
        try:
            db.session.delete(goal)
            db.session.commit()
            flash(_('Meta removida com sucesso.'), 'success')
        except Exception:
            db.session.rollback()
            flash(_('Erro ao remover meta financeira.'), 'error')
    return redirect(url_for('goals.index'))

@goals_bp.route('/goals/update/<int:id>', methods=['POST'])
@login_required
def update_goal(id):
    goal = db.session.get(Goal, id)
    if goal and goal.user_id == current_user.id:
        data = request.form
        try:
            updated_amount = float(data['current_amount'])
            if updated_amount < 0:
                raise ValueError
            goal.current_amount = updated_amount
            db.session.commit()
            flash(_('Meta atualizada com sucesso.'), 'success')
        except ValueError:
            db.session.rollback()
            flash(_('O valor atual não pode ser negativo.'), 'error')
        except Exception:
            db.session.rollback()
            flash(_('Erro ao atualizar meta financeira.'), 'error')
             
    return redirect(url_for('goals.index'))

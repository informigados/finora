from flask import Blueprint, request, redirect, url_for, render_template, flash
from flask_login import login_required, current_user
from flask.typing import ResponseReturnValue
from flask_babel import gettext as _
from models.goal import Goal
from database.db import db
from datetime import datetime
from services.ownership import get_owned_or_none
from services.profile_service import record_activity, record_system_event

goals_bp = Blueprint('goals', __name__)

@goals_bp.route('/goals')
@login_required
def index() -> ResponseReturnValue:
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    return render_template('goals.html', goals=goals)

@goals_bp.route('/goals/add', methods=['POST'])
@login_required
def add_goal() -> ResponseReturnValue:
    data = request.form
    name = (data.get('name') or '').strip()
    if not name:
        flash(_('Nome da meta é obrigatório.'), 'error')
        return redirect(url_for('goals.index'))

    try:
        target_amount = float(data['target_amount'])
        current_amount = float(data.get('current_amount', 0))
    except ValueError:
        flash(_('Os valores da meta devem ser válidos e maiores que zero.'), 'error')
        return redirect(url_for('goals.index'))

    if target_amount <= 0 or current_amount < 0:
        flash(_('Os valores da meta devem ser válidos e maiores que zero.'), 'error')
        return redirect(url_for('goals.index'))

    deadline = None
    if data.get('deadline'):
        try:
            deadline = datetime.strptime(data['deadline'], '%Y-%m-%d').date()
        except ValueError:
            flash(_('Data limite inválida.'), 'error')
            return redirect(url_for('goals.index'))

    try:
        new_goal = Goal(
            name=name,
            target_amount=target_amount,
            current_amount=current_amount,
            deadline=deadline,
            user_id=current_user.id
        )
        db.session.add(new_goal)
        record_activity(
            current_user,
            'goals',
            'goal_created',
            'Meta criada com sucesso.',
            details={'name': new_goal.name, 'target_amount': new_goal.target_amount},
            ip_address=request.remote_addr,
            commit=False,
        )
        db.session.commit()
        flash(_('Meta criada com sucesso.'), 'success')
    except Exception:
        db.session.rollback()
        record_system_event(
            'error',
            'goals',
            'Falha ao adicionar meta financeira.',
            user=current_user,
            event_code='goal_create_failed',
            details={'name': name},
        )
        flash(_('Erro ao adicionar meta financeira.'), 'error')
        
    return redirect(url_for('goals.index'))

@goals_bp.route('/goals/delete/<int:id>', methods=['POST'])
@login_required
def delete_goal(id: int) -> ResponseReturnValue:
    goal = get_owned_or_none(Goal, id, current_user.id)
    if goal:
        goal_name = goal.name
        try:
            record_activity(
                current_user,
                'goals',
                'goal_deleted',
                'Meta removida com sucesso.',
                details={'name': goal_name},
                ip_address=request.remote_addr,
                commit=False,
            )
            db.session.delete(goal)
            db.session.commit()
            flash(_('Meta removida com sucesso.'), 'success')
        except Exception:
            db.session.rollback()
            record_system_event(
                'error',
                'goals',
                'Falha ao remover meta financeira.',
                user=current_user,
                event_code='goal_delete_failed',
                details={'goal_id': id},
            )
            flash(_('Erro ao remover meta financeira.'), 'error')
    return redirect(url_for('goals.index'))

@goals_bp.route('/goals/update/<int:id>', methods=['POST'])
@login_required
def update_goal(id: int) -> ResponseReturnValue:
    goal = get_owned_or_none(Goal, id, current_user.id)
    if goal:
        data = request.form
        try:
            name = (data.get('name') or goal.name or '').strip()
            if not name:
                flash(_('Nome da meta é obrigatório.'), 'error')
                return redirect(url_for('goals.index'))

            target_amount_raw = (data.get('target_amount') or '').strip()
            current_amount_raw = (data.get('current_amount') or '').strip()

            target_amount = float(target_amount_raw) if target_amount_raw else float(goal.target_amount)
            current_amount = float(current_amount_raw) if current_amount_raw else float(goal.current_amount)
            if target_amount <= 0 or current_amount < 0:
                raise ValueError

            deadline = goal.deadline
            if 'deadline' in data:
                deadline = None
                if data.get('deadline'):
                    deadline = datetime.strptime(data['deadline'], '%Y-%m-%d').date()

            goal.name = name
            goal.target_amount = target_amount
            goal.current_amount = current_amount
            goal.deadline = deadline
            record_activity(
                current_user,
                'goals',
                'goal_updated',
                'Meta atualizada com sucesso.',
                details={
                    'name': goal.name,
                    'target_amount': goal.target_amount,
                    'current_amount': goal.current_amount,
                    'deadline': goal.deadline.isoformat() if goal.deadline else None,
                },
                ip_address=request.remote_addr,
                commit=False,
            )
            db.session.commit()
            flash(_('Meta atualizada com sucesso.'), 'success')
        except ValueError:
            flash(_('Os valores da meta devem ser válidos e maiores que zero.'), 'error')
        except Exception:
            db.session.rollback()
            record_system_event(
                'error',
                'goals',
                'Falha ao atualizar meta financeira.',
                user=current_user,
                event_code='goal_update_failed',
                details={'goal_id': id},
            )
            flash(_('Erro ao atualizar meta financeira.'), 'error')
             
    return redirect(url_for('goals.index'))

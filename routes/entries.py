from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_babel import gettext as _
from models.finance import Finance
from models.recurring import RecurringEntry
from database.db import db
from services.validators import validate_finance_data
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

entries_bp = Blueprint('entries', __name__)
VALID_ENTRY_TYPES = {'Receita', 'Despesa'}
VALID_ENTRY_STATUS = {'Pago', 'Pendente', 'Atrasado'}


def _redirect_dashboard_context(fallback_year=None, fallback_month=None):
    year = request.form.get('redirect_year', type=int)
    month = request.form.get('redirect_month', type=int)
    page = request.form.get('redirect_page', type=int)

    if not year or not month:
        year = fallback_year
        month = fallback_month

    if year and month and 1 <= month <= 12:
        route_args = {'year': year, 'month': month}
        if page and page > 1:
            route_args['page'] = page
        return redirect(url_for('dashboard.view_month', **route_args))

    return redirect(url_for('dashboard.index'))


@entries_bp.route('/entries/add', methods=['POST'])
@login_required
def add_entry():
    data = request.form
    try:
        validation_errors = validate_finance_data(data)
        if validation_errors:
            flash(_(validation_errors[0]), 'error')
            return _redirect_dashboard_context()

        description = (data.get('description') or '').strip()

        # Validate critical numeric fields
        try:
            val = float(data['value'])
            if val < 0:
                raise ValueError("Value cannot be negative.")
        except ValueError:
            flash(_('Valor inválido. Insira um número válido e positivo.'), 'error')
            return _redirect_dashboard_context()
            
        entry_type = data.get('type')
        entry_status = data.get('status')
        if entry_type not in VALID_ENTRY_TYPES:
            flash(_('Tipo de lançamento inválido.'), 'error')
            return _redirect_dashboard_context()
        if entry_status not in VALID_ENTRY_STATUS:
            flash(_('Status de lançamento inválido.'), 'error')
            return _redirect_dashboard_context()

        due_d = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
        pay_d = datetime.strptime(data['payment_date'], '%Y-%m-%d').date() if data.get('payment_date') else None

        # 1. Create the initial entry
        new_entry = Finance(
            description=description,
            value=val,
            category=data['category'],
            type=entry_type,
            status=entry_status,
            due_date=due_d,
            payment_date=pay_d,
            observations=data.get('observations'),
            user_id=current_user.id
        )
        db.session.add(new_entry)
        
        # 2. Handle Recurrence
        if data.get('is_recurring') == 'on':
            freq = data.get('frequency')
            start_date = new_entry.due_date
            
            # Calculate next run date
            next_run = start_date
            if freq == 'Diário':
                next_run += timedelta(days=1)
            elif freq == 'Semanal':
                next_run += timedelta(weeks=1)
            elif freq == 'Mensal':
                next_run += relativedelta(months=1)
            elif freq == 'Anual':
                next_run += relativedelta(years=1)
            
            end_d = datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None
                
            if freq not in {'Diário', 'Semanal', 'Mensal', 'Anual'}:
                flash(_('Frequência de recorrência inválida.'), 'error')
                db.session.rollback()
                return _redirect_dashboard_context()

            recurring = RecurringEntry(
                description=new_entry.description,
                value=new_entry.value,
                category=new_entry.category,
                type=new_entry.type,
                frequency=freq,
                start_date=start_date,
                next_run_date=next_run,
                end_date=end_d,
                user_id=current_user.id
            )
            db.session.add(recurring)
            flash(_('Lançamento e recorrência adicionados com sucesso!'), 'success')
        else:
            flash(_('Lançamento adicionado com sucesso!'), 'success')
            
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(_('Erro ao adicionar lançamento. Verifique os dados e tente novamente.'), 'error')
        
    return _redirect_dashboard_context()

@entries_bp.route('/entries/delete/<int:id>', methods=['POST'])
@login_required
def delete_entry(id):
    entry = db.session.get(Finance, id)
    fallback_year = entry.due_date.year if entry else None
    fallback_month = entry.due_date.month if entry else None

    if entry and entry.user_id == current_user.id:
        try:
            db.session.delete(entry)
            db.session.commit()
            flash(_('Lançamento excluído com sucesso!'), 'success')
        except Exception:
            db.session.rollback()
            flash(_('Erro ao excluir lançamento.'), 'error')
    return _redirect_dashboard_context(fallback_year=fallback_year, fallback_month=fallback_month)

@entries_bp.route('/entries/edit/<int:id>', methods=['POST'])
@login_required
def edit_entry(id):
    entry = db.session.get(Finance, id)
    fallback_year = entry.due_date.year if entry else None
    fallback_month = entry.due_date.month if entry else None

    if entry and entry.user_id == current_user.id:
        data = request.form
        try:
            validation_errors = validate_finance_data(data)
            if validation_errors:
                flash(_(validation_errors[0]), 'error')
                return _redirect_dashboard_context(fallback_year=fallback_year, fallback_month=fallback_month)

            try:
                val = float(data['value'])
                if val < 0:
                    raise ValueError("Value cannot be negative.")
            except ValueError:
                flash(_('Valor inválido. Insira um número válido e positivo.'), 'error')
                return _redirect_dashboard_context(fallback_year=fallback_year, fallback_month=fallback_month)

            entry_type = data.get('type')
            entry_status = data.get('status')
            if entry_type not in VALID_ENTRY_TYPES:
                flash(_('Tipo de lançamento inválido.'), 'error')
                return _redirect_dashboard_context(fallback_year=fallback_year, fallback_month=fallback_month)
            if entry_status not in VALID_ENTRY_STATUS:
                flash(_('Status de lançamento inválido.'), 'error')
                return _redirect_dashboard_context(fallback_year=fallback_year, fallback_month=fallback_month)

            description = (data.get('description') or '').strip()
            if not description:
                flash(_('Descrição é obrigatória.'), 'error')
                return _redirect_dashboard_context(fallback_year=fallback_year, fallback_month=fallback_month)

            entry.description = description
            entry.value = val
            entry.category = data['category']
            entry.type = entry_type
            entry.status = entry_status
            entry.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
            entry.payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d').date() if data.get('payment_date') else None
            entry.observations = data.get('observations')
            db.session.commit()
            flash(_('Lançamento atualizado com sucesso!'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Erro ao atualizar lançamento.'), 'error')
            
    return _redirect_dashboard_context(fallback_year=fallback_year, fallback_month=fallback_month)

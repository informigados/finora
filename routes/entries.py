from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask.typing import ResponseReturnValue
from flask_babel import gettext as _
from models.finance import Finance
from models.recurring import RecurringEntry
from database.db import db
from services.ownership import get_owned_or_none
from services.recurring_service import VALID_RECURRENCE_FREQUENCIES, get_next_run_date
from services.validators import parse_finance_form
from datetime import datetime

entries_bp = Blueprint('entries', __name__)


def _redirect_dashboard_context(
    fallback_year: int | None = None,
    fallback_month: int | None = None,
) -> ResponseReturnValue:
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
def add_entry() -> ResponseReturnValue:
    data = request.form
    try:
        payload, validation_errors = parse_finance_form(data)
        if validation_errors:
            flash(_(validation_errors[0]), 'error')
            return _redirect_dashboard_context()

        # 1. Create the initial entry
        new_entry = Finance(
            description=payload['description'],
            value=payload['value'],
            category=payload['category'],
            type=payload['type'],
            status=payload['status'],
            due_date=payload['due_date'],
            payment_date=payload['payment_date'],
            observations=payload['observations'],
            user_id=current_user.id
        )
        db.session.add(new_entry)
        
        # 2. Handle Recurrence
        if data.get('is_recurring') == 'on':
            freq = data.get('frequency')
            start_date = new_entry.due_date

            if freq not in VALID_RECURRENCE_FREQUENCIES:
                flash(_('Frequência de recorrência inválida.'), 'error')
                db.session.rollback()
                return _redirect_dashboard_context()

            next_run = get_next_run_date(start_date, freq)
            if not next_run:
                flash(_('Frequência de recorrência inválida.'), 'error')
                db.session.rollback()
                return _redirect_dashboard_context()

            end_d = (
                datetime.strptime(data['end_date'], '%Y-%m-%d').date()
                if data.get('end_date')
                else None
            )

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
    except Exception:
        db.session.rollback()
        flash(_('Erro ao adicionar lançamento. Verifique os dados e tente novamente.'), 'error')
        
    return _redirect_dashboard_context()

@entries_bp.route('/entries/delete/<int:id>', methods=['POST'])
@login_required
def delete_entry(id: int) -> ResponseReturnValue:
    entry = get_owned_or_none(Finance, id, current_user.id)
    fallback_year = entry.due_date.year if entry else None
    fallback_month = entry.due_date.month if entry else None

    if entry:
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
def edit_entry(id: int) -> ResponseReturnValue:
    entry = get_owned_or_none(Finance, id, current_user.id)
    fallback_year = entry.due_date.year if entry else None
    fallback_month = entry.due_date.month if entry else None

    if entry:
        data = request.form
        try:
            payload, validation_errors = parse_finance_form(data)
            if validation_errors:
                flash(_(validation_errors[0]), 'error')
                return _redirect_dashboard_context(fallback_year=fallback_year, fallback_month=fallback_month)

            entry.description = payload['description']
            entry.value = payload['value']
            entry.category = payload['category']
            entry.type = payload['type']
            entry.status = payload['status']
            entry.due_date = payload['due_date']
            entry.payment_date = payload['payment_date']
            entry.observations = payload['observations']
            db.session.commit()
            flash(_('Lançamento atualizado com sucesso!'), 'success')
        except Exception:
            db.session.rollback()
            flash(_('Erro ao atualizar lançamento.'), 'error')
            
    return _redirect_dashboard_context(fallback_year=fallback_year, fallback_month=fallback_month)

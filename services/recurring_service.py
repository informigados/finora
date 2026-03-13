import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from database.db import db
from models.recurring import RecurringEntry
from models.finance import Finance

logger = logging.getLogger(__name__)
VALID_RECURRENCE_FREQUENCIES = {'Diário', 'Semanal', 'Mensal', 'Anual'}


def get_next_run_date(start_date, frequency):
    if frequency == 'Diário':
        return start_date + timedelta(days=1)
    if frequency == 'Semanal':
        return start_date + timedelta(weeks=1)
    if frequency == 'Mensal':
        return start_date + relativedelta(months=1)
    if frequency == 'Anual':
        return start_date + relativedelta(years=1)
    return None


def _advance_next_run_date(entry):
    next_run_date = get_next_run_date(entry.next_run_date, entry.frequency)
    if not next_run_date:
        return False

    entry.next_run_date = next_run_date
    return True


def process_recurring_entries(user_id, commit=True):
    """
    Checks for active recurring entries that need to be processed
    and creates the corresponding Finance entries.
    """
    today = datetime.now().date()
    
    # Get active recurring entries due for processing
    recurring_entries = RecurringEntry.query.filter(
        RecurringEntry.user_id == user_id,
        RecurringEntry.active.is_(True),
        RecurringEntry.next_run_date <= today
    ).all()
    
    processed_count = 0
    
    for entry in recurring_entries:
        while entry.active and entry.next_run_date <= today:
            if entry.end_date and entry.next_run_date > entry.end_date:
                entry.active = False
                break

            # Create one finance entry for each pending occurrence.
            new_finance = Finance(
                description=entry.description,
                value=entry.value,
                category=entry.category,
                type=entry.type,
                status='Pendente', # Default status for recurring generated entries
                due_date=entry.next_run_date,
                user_id=entry.user_id,
                observations=f"Gerado automaticamente (Recorrente: {entry.frequency})"
            )
            db.session.add(new_finance)
            entry.last_run_date = entry.next_run_date
            processed_count += 1

            if not _advance_next_run_date(entry):
                entry.active = False
                break

            if entry.end_date and entry.next_run_date > entry.end_date:
                entry.active = False
        
    if processed_count > 0 and commit:
        db.session.commit()
        
    return processed_count


def process_all_recurring_entries():
    today = datetime.now().date()
    user_rows = db.session.query(RecurringEntry.user_id).filter(
        RecurringEntry.active.is_(True),
        RecurringEntry.next_run_date <= today
    ).distinct().all()

    processed_entries = 0
    affected_users = 0

    for row in user_rows:
        user_id = row[0]
        try:
            count = process_recurring_entries(user_id)
        except Exception:
            db.session.rollback()
            logger.exception('Falha ao processar recorrencias pendentes do usuario %s.', user_id)
            continue

        if count > 0:
            processed_entries += count
            affected_users += 1

    return {
        'processed_entries': processed_entries,
        'affected_users': affected_users,
    }

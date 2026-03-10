from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from database.db import db
from models.recurring import RecurringEntry
from models.finance import Finance


def _advance_next_run_date(entry):
    if entry.frequency == 'Diário':
        entry.next_run_date += timedelta(days=1)
        return True
    if entry.frequency == 'Semanal':
        entry.next_run_date += timedelta(weeks=1)
        return True
    if entry.frequency == 'Mensal':
        entry.next_run_date += relativedelta(months=1)
        return True
    if entry.frequency == 'Anual':
        entry.next_run_date += relativedelta(years=1)
        return True
    return False


def process_recurring_entries(user_id):
    """
    Checks for active recurring entries that need to be processed
    and creates the corresponding Finance entries.
    """
    today = datetime.now().date()
    
    # Get active recurring entries due for processing
    recurring_entries = RecurringEntry.query.filter(
        RecurringEntry.user_id == user_id,
        RecurringEntry.active == True,
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
        
    if processed_count > 0:
        db.session.commit()
        
    return processed_count

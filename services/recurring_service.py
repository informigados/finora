from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from database.db import db
from models.recurring import RecurringEntry
from models.finance import Finance

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
        # Create the finance entry
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
        
        # Update recurring entry
        entry.last_run_date = entry.next_run_date
        
        # Calculate next run date
        if entry.frequency == 'Diário':
            entry.next_run_date += timedelta(days=1)
        elif entry.frequency == 'Semanal':
            entry.next_run_date += timedelta(weeks=1)
        elif entry.frequency == 'Mensal':
            entry.next_run_date += relativedelta(months=1)
        elif entry.frequency == 'Anual':
            entry.next_run_date += relativedelta(years=1)
            
        # Check if we passed the end_date
        if entry.end_date and entry.next_run_date > entry.end_date:
            entry.active = False
            
        processed_count += 1
        
    if processed_count > 0:
        db.session.commit()
        
    return processed_count

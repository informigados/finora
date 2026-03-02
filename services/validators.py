def validate_finance_data(data):
    errors = []
    if not data.get('description'):
        errors.append("Descrição é obrigatória")
    
    try:
        val = float(data.get('value', 0))
        if val < 0:
             # usually value is positive, type determines sign. But let's allow negative if user wants corrections.
             pass
    except ValueError:
        errors.append("Valor deve ser um número")
        
    if not data.get('due_date'):
        errors.append("Data de vencimento é obrigatória")
        
    if not data.get('category'):
        errors.append("Categoria é obrigatória")
        
    return errors

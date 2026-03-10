def validate_finance_data(data, require_description=True):
    errors = []

    description = (data.get('description') or '').strip()
    if require_description and not description:
        errors.append("Descrição é obrigatória.")

    raw_value = (data.get('value') or '').strip()
    if not raw_value:
        errors.append("Valor inválido. Insira um número válido e positivo.")
    else:
        try:
            value = float(raw_value)
            if value < 0:
                errors.append("Valor inválido. Insira um número válido e positivo.")
        except (TypeError, ValueError):
            errors.append("Valor inválido. Insira um número válido e positivo.")

    if not (data.get('due_date') or '').strip():
        errors.append("Data de vencimento é obrigatória.")

    if not (data.get('category') or '').strip():
        errors.append("Categoria é obrigatória.")

    return errors

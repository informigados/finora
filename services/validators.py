from datetime import datetime

from services.catalogs import (
    normalize_finance_category,
    normalize_payment_method,
    resolve_finance_category_selection,
)


VALID_ENTRY_TYPES = {'Receita', 'Despesa'}
VALID_ENTRY_STATUS = {'Pago', 'Pendente', 'Atrasado'}


def validate_finance_data(data, require_description=True):
    errors = []

    description = (data.get('description') or '').strip()
    if require_description and not description:
        errors.append("Descrição é obrigatória.")
    elif description and len(description) > 100:
        errors.append("Descrição deve ter no máximo 100 caracteres.")

    raw_value = (data.get('value') or '').strip()
    if not raw_value:
        errors.append("Valor inválido. Insira um número válido e positivo.")
    else:
        try:
            value = float(raw_value)
            if value <= 0:
                errors.append("Valor deve ser maior que zero.")
        except (TypeError, ValueError):
            errors.append("Valor inválido. Insira um número válido e positivo.")

    if not (data.get('due_date') or '').strip():
        errors.append("Data de vencimento é obrigatória.")

    entry_type = (data.get('type') or '').strip()

    if not (data.get('category') or '').strip():
        errors.append("Categoria é obrigatória.")
    elif len((data.get('category') or '').strip()) > 50:
        errors.append("Categoria deve ter no máximo 50 caracteres.")
    elif normalize_finance_category(data.get('category'), entry_type=entry_type) is None:
        errors.append("Categoria inválida. Selecione uma categoria permitida.")

    raw_subcategory = (data.get('subcategory') or '').strip()
    if raw_subcategory and len(raw_subcategory) > 80:
        errors.append("Subcategoria deve ter no máximo 80 caracteres.")
    elif raw_subcategory:
        normalized_category, normalized_subcategory = resolve_finance_category_selection(
            entry_type=entry_type,
            category_value=data.get('category'),
            subcategory_value=raw_subcategory,
        )
        if normalized_category is None:
            errors.append("Categoria inválida. Selecione uma categoria permitida.")
        elif normalized_subcategory is None:
            errors.append("Subcategoria inválida. Selecione uma subcategoria permitida.")

    raw_payment_method = (data.get('payment_method') or '').strip()
    if raw_payment_method and len(raw_payment_method) > 40:
        errors.append("Forma de pagamento/recebimento deve ter no máximo 40 caracteres.")
    elif raw_payment_method and normalize_payment_method(raw_payment_method) is None:
        errors.append("Forma de pagamento/recebimento inválida.")

    if entry_type not in VALID_ENTRY_TYPES:
        errors.append("Tipo de lançamento inválido.")

    if (data.get('status') or '').strip() not in VALID_ENTRY_STATUS:
        errors.append("Status de lançamento inválido.")

    return errors


def parse_finance_form(data):
    errors = validate_finance_data(data)
    if errors:
        return None, errors

    try:
        due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None, ["Data de vencimento é obrigatória."]

    payment_date = None
    if data.get('payment_date'):
        try:
            payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None, ["Data de pagamento inválida."]

    normalized_category, normalized_subcategory = resolve_finance_category_selection(
        entry_type=(data.get('type') or '').strip(),
        category_value=data.get('category'),
        subcategory_value=data.get('subcategory'),
    )
    if normalized_category is None:
        return None, ["Categoria inválida. Selecione uma categoria permitida."]

    if (data.get('subcategory') or '').strip() and normalized_subcategory is None:
        return None, ["Subcategoria inválida. Selecione uma subcategoria permitida."]

    payload = {
        'description': (data.get('description') or '').strip(),
        'value': float((data.get('value') or '').strip()),
        'category': normalized_category,
        'subcategory': normalized_subcategory,
        'type': (data.get('type') or '').strip(),
        'status': (data.get('status') or '').strip(),
        'due_date': due_date,
        'payment_date': payment_date,
        'payment_method': normalize_payment_method(data.get('payment_method')),
        'observations': (data.get('observations') or '').strip() or None,
    }
    return payload, []

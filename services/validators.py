from datetime import datetime

from services.catalogs import normalize_finance_category


VALID_ENTRY_TYPES = {'Receita', 'Despesa'}
VALID_ENTRY_STATUS = {'Pago', 'Pendente', 'Atrasado'}


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
    elif len((data.get('category') or '').strip()) > 50:
        errors.append("Categoria deve ter no máximo 50 caracteres.")
    elif normalize_finance_category(data.get('category')) is None:
        errors.append("Categoria inválida. Selecione uma categoria permitida.")

    if (data.get('description') or '').strip() and len((data.get('description') or '').strip()) > 100:
        errors.append("Descrição deve ter no máximo 100 caracteres.")

    if (data.get('type') or '').strip() not in VALID_ENTRY_TYPES:
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

    payload = {
        'description': (data.get('description') or '').strip(),
        'value': float((data.get('value') or '').strip()),
        'category': normalize_finance_category(data.get('category')),
        'type': (data.get('type') or '').strip(),
        'status': (data.get('status') or '').strip(),
        'due_date': due_date,
        'payment_date': payment_date,
        'observations': (data.get('observations') or '').strip() or None,
    }
    return payload, []

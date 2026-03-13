from __future__ import annotations

import unicodedata


DEFAULT_FINANCE_CATEGORIES = (
    'Alimentação',
    'Moradia',
    'Transporte',
    'Lazer',
    'Saúde',
    'Educação',
    'Salário',
    'Investimento',
)

_CATEGORY_ALIASES = {
    'alimentacao': 'Alimentação',
    'alimentacaoes': 'Alimentação',
    'food': 'Alimentação',
    'moradia': 'Moradia',
    'housing': 'Moradia',
    'transporte': 'Transporte',
    'transport': 'Transporte',
    'transportation': 'Transporte',
    'lazer': 'Lazer',
    'leisure': 'Lazer',
    'saude': 'Saúde',
    'health': 'Saúde',
    'educacao': 'Educação',
    'education': 'Educação',
    'salario': 'Salário',
    'salary': 'Salário',
    'investimento': 'Investimento',
    'investment': 'Investimento',
}


def _normalize_category_key(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value or '')
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip().lower().replace(' ', '')


def normalize_finance_category(value: str | None) -> str | None:
    key = _normalize_category_key(value or '')
    if not key:
        return None

    if key in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[key]

    for category in DEFAULT_FINANCE_CATEGORIES:
        if _normalize_category_key(category) == key:
            return category
    return None


def is_allowed_finance_category(value: str | None) -> bool:
    return normalize_finance_category(value) is not None

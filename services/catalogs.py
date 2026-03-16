from __future__ import annotations

import unicodedata


def _normalize_token(value: str | None) -> str:
    normalized = unicodedata.normalize('NFKD', value or '')
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip().lower().replace('_', ' ').replace('-', '').replace('/', '')


FINANCE_CATEGORY_TREE = {
    'Receita': {
        'Trabalho': (
            'Salário',
            'Pró-labore',
            'Freelance / Serviços',
            'Comissões',
            'Bônus',
        ),
        'Rendimentos': (
            'Juros',
            'Dividendos',
            'Rendimentos de investimentos',
        ),
        'Aluguéis': (
            'Aluguel de imóvel',
            'Aluguel de bens',
        ),
        'Vendas': (
            'Venda de produtos',
            'Venda de bens',
        ),
        'Outros': (
            'Reembolsos',
            'Doações recebidas',
            'Outras receitas',
        ),
    },
    'Despesa': {
        'Moradia': (
            'Aluguel',
            'Financiamento imobiliário',
            'Condomínio',
            'Manutenção do imóvel',
            'Reforma',
        ),
        'Utilidades': (
            'Energia elétrica',
            'Água',
            'Gás',
            'Coleta de lixo',
            'Taxas municipais',
        ),
        'Internet/Comunicação': (
            'Internet',
            'Telefonia móvel',
            'Telefonia fixa',
            'TV / Streaming',
        ),
        'Alimentação': (
            'Supermercado',
            'Restaurantes',
            'Delivery',
            'Padaria / café',
        ),
        'Transporte': (
            'Combustível',
            'Transporte público',
            'Uber / Táxi',
            'Manutenção do veículo',
            'Seguro do veículo',
            'Estacionamento',
            'Pedágio',
        ),
        'Saúde': (
            'Plano de saúde',
            'Consultas',
            'Exames',
            'Medicamentos',
            'Terapias',
            'Academia',
        ),
        'Educação': (
            'Escola',
            'Faculdade',
            'Cursos',
            'Livros',
            'Material escolar',
        ),
        'Lazer': (
            'Cinema',
            'Shows / eventos',
            'Viagens',
            'Hobbies',
            'Jogos',
        ),
        'Compras/Consumo': (
            'Roupas / acessórios',
            'Eletrônicos',
            'Casa / decoração',
            'Presentes',
            'Compras online',
        ),
        'Financeiro': (
            'Fatura do cartão',
            'Juros bancários',
            'Tarifas bancárias',
        ),
        'Empréstimos/Financiamentos': (
            'Parcelas de empréstimos',
            'Financiamento de veículo',
            'Outros financiamentos',
        ),
        'Impostos/Tributos': (
            'Imposto de renda',
            'IPTU',
            'IPVA',
            'Taxas governamentais',
            'Multas',
        ),
        'Seguros': (
            'Seguro de vida',
            'Seguro veicular',
            'Seguro residencial',
            'Outros seguros',
        ),
        'Investimentos': (
            'Aportes',
            'Taxas de corretagem',
            'Taxas de investimento',
        ),
        'Pessoal/Família': (
            'Cuidados pessoais',
            'Salão / estética',
            'Mesada',
            'Cuidados infantis',
        ),
        'Outros': (
            'Despesas diversas',
        ),
    },
}

DEFAULT_FINANCE_CATEGORIES = tuple(FINANCE_CATEGORY_TREE['Despesa'].keys())
PAYMENT_METHOD_OPTIONS = (
    'Cartão de Crédito',
    'Cartão de Débito',
    'Transferência / PIX',
    'Dinheiro',
    'Outra Forma ou Meio',
)

_CATEGORY_ALIASES_BY_TYPE = {
    'Receita': {
        'trabalho': 'Trabalho',
        'work': 'Trabalho',
        'employment': 'Trabalho',
        'rendimentos': 'Rendimentos',
        'income': 'Rendimentos',
        'earnings': 'Rendimentos',
        'alugueis': 'Aluguéis',
        'rentals': 'Aluguéis',
        'vendas': 'Vendas',
        'sales': 'Vendas',
        'outros': 'Outros',
        'other': 'Outros',
        'others': 'Outros',
        'salario': 'Trabalho',
        'salary': 'Trabalho',
        'prolabore': 'Trabalho',
        'freelance': 'Trabalho',
        'services': 'Trabalho',
        'commissions': 'Trabalho',
        'bonus': 'Trabalho',
        'bonuses': 'Trabalho',
        'juros': 'Rendimentos',
        'interest': 'Rendimentos',
        'dividends': 'Rendimentos',
        'investimento': 'Rendimentos',
        'investment': 'Rendimentos',
        'aluguel': 'Aluguéis',
        'reimbursements': 'Outros',
        'donationsreceived': 'Outros',
    },
    'Despesa': {
        'moradia': 'Moradia',
        'housing': 'Moradia',
        'utilidades': 'Utilidades',
        'utilities': 'Utilidades',
        'internetcomunicacao': 'Internet/Comunicação',
        'communication': 'Internet/Comunicação',
        'alimentacao': 'Alimentação',
        'food': 'Alimentação',
        'transporte': 'Transporte',
        'transport': 'Transporte',
        'transportation': 'Transporte',
        'saude': 'Saúde',
        'health': 'Saúde',
        'educacao': 'Educação',
        'education': 'Educação',
        'lazer': 'Lazer',
        'leisure': 'Lazer',
        'entretenimento': 'Lazer',
        'comprasconsumo': 'Compras/Consumo',
        'shopping': 'Compras/Consumo',
        'consumption': 'Compras/Consumo',
        'financeiro': 'Financeiro',
        'financial': 'Financeiro',
        'emprestimosfinanciamentos': 'Empréstimos/Financiamentos',
        'loans': 'Empréstimos/Financiamentos',
        'financing': 'Empréstimos/Financiamentos',
        'impostostributos': 'Impostos/Tributos',
        'taxes': 'Impostos/Tributos',
        'seguros': 'Seguros',
        'insurance': 'Seguros',
        'investimentos': 'Investimentos',
        'investments': 'Investimentos',
        'investimento': 'Investimentos',
        'investment': 'Investimentos',
        'pessoalfamilia': 'Pessoal/Família',
        'personal': 'Pessoal/Família',
        'family': 'Pessoal/Família',
        'outros': 'Outros',
        'other': 'Outros',
        'others': 'Outros',
    },
}

_LEGACY_CATEGORY_FALLBACKS = {
    'alimentacao': ('Despesa', 'Alimentação', None),
    'food': ('Despesa', 'Alimentação', None),
    'moradia': ('Despesa', 'Moradia', None),
    'housing': ('Despesa', 'Moradia', None),
    'transporte': ('Despesa', 'Transporte', None),
    'transport': ('Despesa', 'Transporte', None),
    'transportation': ('Despesa', 'Transporte', None),
    'lazer': ('Despesa', 'Lazer', None),
    'leisure': ('Despesa', 'Lazer', None),
    'saude': ('Despesa', 'Saúde', None),
    'health': ('Despesa', 'Saúde', None),
    'educacao': ('Despesa', 'Educação', None),
    'education': ('Despesa', 'Educação', None),
    'salario': ('Receita', 'Trabalho', 'Salário'),
    'salary': ('Receita', 'Trabalho', 'Salário'),
}

_PAYMENT_METHOD_ALIASES = {
    'cartaodecredito': 'Cartão de Crédito',
    'creditcard': 'Cartão de Crédito',
    'cartaodedebito': 'Cartão de Débito',
    'debitcard': 'Cartão de Débito',
    'transferencia': 'Transferência / PIX',
    'transferenciapix': 'Transferência / PIX',
    'pix': 'Transferência / PIX',
    'transfer': 'Transferência / PIX',
    'banktransfer': 'Transferência / PIX',
    'dinheiro': 'Dinheiro',
    'cash': 'Dinheiro',
    'outraformaoumeio': 'Outra Forma ou Meio',
    'outraforma': 'Outra Forma ou Meio',
    'other': 'Outra Forma ou Meio',
    'othermethod': 'Outra Forma ou Meio',
}

_SUBCATEGORY_EXTRA_ALIASES = {
    'Salário': ('salary', 'salario'),
    'Pró-labore': ('prolabore', 'ownerdraw'),
    'Freelance / Serviços': ('freelance', 'services'),
    'Comissões': ('commissions',),
    'Bônus': ('bonus', 'bonuses'),
    'Juros': ('interest',),
    'Dividendos': ('dividends',),
    'Rendimentos de investimentos': ('investmentreturns', 'investmentincome'),
    'Aluguel de imóvel': ('propertyrent',),
    'Aluguel de bens': ('assetrent',),
    'Venda de produtos': ('productsale',),
    'Venda de bens': ('assetsale',),
    'Reembolsos': ('reimbursements',),
    'Doações recebidas': ('donationsreceived',),
    'Outras receitas': ('otherincome',),
    'Energia elétrica': ('electricity',),
    'Água': ('water',),
    'Gás': ('gas',),
    'Internet': ('internet',),
    'Telefonia móvel': ('mobilephone',),
    'Telefonia fixa': ('landline',),
    'TV / Streaming': ('tvstreaming',),
    'Supermercado': ('groceries',),
    'Restaurantes': ('restaurants',),
    'Delivery': ('delivery',),
    'Padaria / café': ('bakerycafe',),
    'Transporte público': ('publictransport',),
    'Uber / Táxi': ('ubertaxi',),
    'Medicamentos': ('medicines',),
    'Academia': ('gym',),
    'Cursos': ('courses',),
    'Livros': ('books',),
    'Material escolar': ('schoolsupplies',),
    'Shows / eventos': ('showsevents',),
    'Viagens': ('travel',),
    'Hobbies': ('hobbies',),
    'Jogos': ('games',),
    'Roupas / acessórios': ('clothingaccessories',),
    'Eletrônicos': ('electronics',),
    'Casa / decoração': ('homedecor',),
    'Presentes': ('gifts',),
    'Compras online': ('onlineshopping',),
    'Fatura do cartão': ('creditcardbill',),
    'Juros bancários': ('bankinterest',),
    'Tarifas bancárias': ('bankfees',),
    'Parcelas de empréstimos': ('loaninstallments',),
    'Financiamento de veículo': ('vehiclefinancing',),
    'Outros financiamentos': ('otherfinancing',),
    'Imposto de renda': ('incometax',),
    'Taxas governamentais': ('governmentfees',),
    'Seguro de vida': ('lifeinsurance',),
    'Seguro veicular': ('vehicleinsurance',),
    'Seguro residencial': ('homeinsurance',),
    'Outros seguros': ('otherinsurance',),
    'Aportes': ('contributions',),
    'Taxas de corretagem': ('brokeragefees',),
    'Taxas de investimento': ('investmentfees',),
    'Cuidados pessoais': ('personalcare',),
    'Salão / estética': ('beauty', 'salon'),
    'Mesada': ('allowance',),
    'Cuidados infantis': ('childcare',),
    'Despesas diversas': ('miscexpenses',),
}


def _build_subcategory_lookup() -> dict[tuple[str, str], tuple[str, str]]:
    lookup: dict[tuple[str, str], tuple[str, str]] = {}

    for entry_type, categories in FINANCE_CATEGORY_TREE.items():
        for category, subcategories in categories.items():
            for subcategory in subcategories:
                normalized_keys = {
                    _normalize_token(subcategory),
                    ' '.join(_normalize_token(subcategory).split()),
                }
                normalized_keys.update(_SUBCATEGORY_EXTRA_ALIASES.get(subcategory, ()))

                for key in normalized_keys:
                    if key:
                        lookup[(entry_type, key)] = (category, subcategory)

    return lookup


_SUBCATEGORY_LOOKUP = _build_subcategory_lookup()


def get_categories_for_type(entry_type: str | None) -> tuple[str, ...]:
    return tuple(FINANCE_CATEGORY_TREE.get(entry_type or '', {}).keys())


def get_subcategories_for_category(entry_type: str | None, category: str | None) -> tuple[str, ...]:
    if not entry_type or not category:
        return ()
    return tuple(FINANCE_CATEGORY_TREE.get(entry_type, {}).get(category, ()))


def get_expense_budget_categories() -> tuple[str, ...]:
    return get_categories_for_type('Despesa')


def get_payment_method_options() -> tuple[str, ...]:
    return PAYMENT_METHOD_OPTIONS


def build_finance_catalog_payload(translator=None) -> dict[str, dict[str, object]]:
    translate = translator or (lambda value: value)
    payload: dict[str, dict[str, object]] = {}

    for entry_type, categories in FINANCE_CATEGORY_TREE.items():
        payload[entry_type] = {
            'label': translate(entry_type),
            'categories': [
                {
                    'value': category,
                    'label': translate(category),
                    'subcategories': [
                        {
                            'value': subcategory,
                            'label': translate(subcategory),
                        }
                        for subcategory in subcategories
                    ],
                }
                for category, subcategories in categories.items()
            ],
        }

    return payload


def build_payment_method_payload(translator=None) -> list[dict[str, str]]:
    translate = translator or (lambda value: value)
    return [
        {
            'value': payment_method,
            'label': translate(payment_method),
        }
        for payment_method in PAYMENT_METHOD_OPTIONS
    ]


def normalize_finance_category(value: str | None, entry_type: str | None = None) -> str | None:
    category, _subcategory = resolve_finance_category_selection(
        entry_type=entry_type,
        category_value=value,
        subcategory_value=None,
    )
    return category


def normalize_finance_subcategory(
    value: str | None,
    entry_type: str | None,
    category: str | None,
) -> str | None:
    if not value or not entry_type or not category:
        return None

    normalized_value = _normalize_token(value)
    available_subcategories = get_subcategories_for_category(entry_type, category)
    for subcategory in available_subcategories:
        if _normalize_token(subcategory) == normalized_value:
            return subcategory

    lookup = _SUBCATEGORY_LOOKUP.get((entry_type, normalized_value))
    if lookup and lookup[0] == category:
        return lookup[1]

    return None


def resolve_finance_category_selection(
    entry_type: str | None,
    category_value: str | None,
    subcategory_value: str | None = None,
) -> tuple[str | None, str | None]:
    normalized_type = entry_type or None
    normalized_category_value = _normalize_token(category_value)
    normalized_subcategory_value = _normalize_token(subcategory_value)

    if normalized_type in FINANCE_CATEGORY_TREE:
        resolved = _resolve_within_type(
            normalized_type,
            normalized_category_value,
            normalized_subcategory_value,
        )
        if resolved != (None, None):
            return resolved

    if normalized_category_value in _LEGACY_CATEGORY_FALLBACKS:
        fallback_type, fallback_category, fallback_subcategory = _LEGACY_CATEGORY_FALLBACKS[normalized_category_value]
        if normalized_type in {None, fallback_type}:
            if subcategory_value:
                normalized_subcategory = normalize_finance_subcategory(
                    subcategory_value,
                    fallback_type,
                    fallback_category,
                )
                return fallback_category, normalized_subcategory
            return fallback_category, fallback_subcategory

    if normalized_subcategory_value:
        for candidate_type in _iter_candidate_types(normalized_type):
            lookup = _SUBCATEGORY_LOOKUP.get((candidate_type, normalized_subcategory_value))
            if lookup:
                return lookup

    if normalized_category_value:
        for candidate_type in _iter_candidate_types(normalized_type):
            lookup = _SUBCATEGORY_LOOKUP.get((candidate_type, normalized_category_value))
            if lookup:
                return lookup

    return None, None


def is_allowed_finance_category(value: str | None, entry_type: str | None = None) -> bool:
    return normalize_finance_category(value, entry_type=entry_type) is not None


def normalize_payment_method(value: str | None) -> str | None:
    normalized_value = _normalize_token(value)
    if not normalized_value:
        return None
    compact_value = normalized_value.replace(' ', '')

    if normalized_value in _PAYMENT_METHOD_ALIASES:
        return _PAYMENT_METHOD_ALIASES[normalized_value]
    if compact_value in _PAYMENT_METHOD_ALIASES:
        return _PAYMENT_METHOD_ALIASES[compact_value]

    for option in PAYMENT_METHOD_OPTIONS:
        option_key = _normalize_token(option)
        if option_key in {normalized_value, compact_value}:
            return option

    return None


def _resolve_within_type(
    entry_type: str,
    normalized_category_value: str,
    normalized_subcategory_value: str,
) -> tuple[str | None, str | None]:
    categories = FINANCE_CATEGORY_TREE.get(entry_type, {})
    aliases = _CATEGORY_ALIASES_BY_TYPE.get(entry_type, {})

    category = None
    if normalized_category_value:
        category = aliases.get(normalized_category_value)
        if category is None:
            for candidate in categories:
                if _normalize_token(candidate) == normalized_category_value:
                    category = candidate
                    break

    if category and normalized_subcategory_value:
        subcategory = normalize_finance_subcategory(
            normalized_subcategory_value,
            entry_type,
            category,
        )
        return category, subcategory

    if category:
        lookup = _SUBCATEGORY_LOOKUP.get((entry_type, normalized_category_value))
        if lookup and lookup[0] == category:
            return lookup
        return category, None

    if normalized_category_value:
        lookup = _SUBCATEGORY_LOOKUP.get((entry_type, normalized_category_value))
        if lookup:
            return lookup

    if normalized_subcategory_value:
        lookup = _SUBCATEGORY_LOOKUP.get((entry_type, normalized_subcategory_value))
        if lookup:
            return lookup

    return None, None


def _iter_candidate_types(entry_type: str | None) -> tuple[str, ...]:
    if entry_type in FINANCE_CATEGORY_TREE:
        return (entry_type,)
    return tuple(FINANCE_CATEGORY_TREE.keys())

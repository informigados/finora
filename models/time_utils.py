from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app, has_app_context


def utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)


def get_app_timezone():
    timezone_name = 'UTC'
    if has_app_context():
        timezone_name = current_app.config.get('APP_TIMEZONE', 'UTC') or 'UTC'

    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return UTC


def current_business_date():
    return datetime.now(get_app_timezone()).date()


def to_app_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(get_app_timezone())


def format_app_datetime(value, fmt='%d/%m/%Y %H:%M'):
    localized = to_app_datetime(value)
    if localized is None:
        return ''
    return localized.strftime(fmt)


def format_app_date(value, fmt='%d/%m/%Y'):
    if value is None:
        return ''
    if isinstance(value, datetime):
        return format_app_datetime(value, fmt)
    if isinstance(value, date):
        return value.strftime(fmt)
    return str(value)

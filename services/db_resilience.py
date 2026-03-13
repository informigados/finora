from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from flask import current_app
from sqlalchemy.exc import DBAPIError, OperationalError

from database.db import db


T = TypeVar('T')


def run_idempotent_db_operation(operation: Callable[[], T]) -> T:
    max_retries = int(current_app.config.get('DB_IDEMPOTENT_MAX_RETRIES', 2) or 2)
    backoff_seconds = float(current_app.config.get('DB_IDEMPOTENT_RETRY_BACKOFF_SECONDS', 0.15) or 0.15)

    for attempt in range(max_retries + 1):
        try:
            return operation()
        except (OperationalError, DBAPIError) as exc:
            db.session.rollback()
            is_retryable = isinstance(exc, OperationalError) or getattr(exc, 'connection_invalidated', False)
            if not is_retryable or attempt >= max_retries:
                raise
            time.sleep(backoff_seconds * (attempt + 1))

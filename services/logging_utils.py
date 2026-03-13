import logging
import os
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler


request_id_context: ContextVar[str] = ContextVar('request_id', default='-')


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_context.get('-')
        return True


def _handler_matches_file(handler, log_path):
    return isinstance(handler, RotatingFileHandler) and getattr(handler, 'baseFilename', None) == log_path


def _configure_stream_handler(app, formatter, request_id_filter):
    stream_handler = next(
        (handler for handler in app.logger.handlers if isinstance(handler, logging.StreamHandler)),
        None,
    )
    if stream_handler is None:
        stream_handler = logging.StreamHandler()
        app.logger.addHandler(stream_handler)

    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(request_id_filter)


def _configure_file_handler(app, formatter, request_id_filter):
    if not app.config.get('LOG_TO_FILE'):
        return

    log_directory = app.config.get('LOG_DIRECTORY')
    log_file_name = app.config.get('LOG_FILE_NAME', 'finora.log')
    if not log_directory or not log_file_name:
        return

    os.makedirs(log_directory, exist_ok=True)
    log_path = os.path.abspath(os.path.join(log_directory, log_file_name))
    file_handler = next(
        (handler for handler in app.logger.handlers if _handler_matches_file(handler, log_path)),
        None,
    )
    if file_handler is None:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max(int(app.config.get('LOG_MAX_BYTES', 1_048_576) or 1_048_576), 1),
            backupCount=max(int(app.config.get('LOG_BACKUP_COUNT', 5) or 5), 1),
            encoding='utf-8',
        )
        app.logger.addHandler(file_handler)

    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_id_filter)


def configure_application_logging(app):
    log_level_name = str(app.config.get('LOG_LEVEL', 'INFO')).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    sqlalchemy_log_level_name = str(app.config.get('SQLALCHEMY_LOG_LEVEL', 'WARNING')).upper()
    sqlalchemy_log_level = getattr(logging, sqlalchemy_log_level_name, logging.WARNING)
    werkzeug_log_level_name = str(app.config.get('WERKZEUG_LOG_LEVEL', log_level_name)).upper()
    werkzeug_log_level = getattr(logging, werkzeug_log_level_name, log_level)
    waitress_log_level_name = str(app.config.get('WAITRESS_LOG_LEVEL', log_level_name)).upper()
    waitress_log_level = getattr(logging, waitress_log_level_name, log_level)
    log_format = app.config.get(
        'LOG_FORMAT',
        '[%(asctime)s] %(levelname)s %(name)s request_id=%(request_id)s %(message)s',
    )

    formatter = logging.Formatter(log_format)
    request_id_filter = RequestIdFilter()

    _configure_stream_handler(app, formatter, request_id_filter)
    _configure_file_handler(app, formatter, request_id_filter)

    for handler in app.logger.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(request_id_filter)

    app.logger.setLevel(log_level)

    logger_levels = {
        'werkzeug': werkzeug_log_level,
        'sqlalchemy.engine': sqlalchemy_log_level,
        'waitress': waitress_log_level,
    }
    for logger_name, logger_level in logger_levels.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logger_level)
        for handler in logger.handlers:
            handler.addFilter(request_id_filter)

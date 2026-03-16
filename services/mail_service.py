import smtplib
from email.message import EmailMessage


def send_email(app, to_address, subject, plain_text_body):
    to_address = (to_address or '').strip()
    if not to_address:
        return {'ok': False, 'reason': 'missing_recipient'}

    mail_server = (app.config.get('MAIL_SERVER') or '').strip()
    mail_port = int(app.config.get('MAIL_PORT', 587) or 587)
    mail_username = (app.config.get('MAIL_USERNAME') or '').strip()
    mail_password = app.config.get('MAIL_PASSWORD') or ''
    mail_use_tls = bool(app.config.get('MAIL_USE_TLS', True))
    mail_use_ssl = bool(app.config.get('MAIL_USE_SSL', False))
    mail_default_sender = (app.config.get('MAIL_DEFAULT_SENDER') or '').strip()
    mail_from_name = (app.config.get('MAIL_FROM_NAME') or 'Finora').strip()

    if not mail_server or not mail_default_sender:
        app.logger.info(
            'Envio de e-mail em modo local. Destino=%s assunto=%s corpo_chars=%s',
            to_address,
            subject,
            len(plain_text_body or ''),
        )
        return {'ok': True, 'delivery': 'log'}

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = f'{mail_from_name} <{mail_default_sender}>'
    message['To'] = to_address
    message.set_content(plain_text_body)

    smtp_client = smtplib.SMTP_SSL if mail_use_ssl else smtplib.SMTP

    try:
        with smtp_client(mail_server, mail_port, timeout=app.config.get('MAIL_TIMEOUT_SECONDS', 10)) as client:
            if not mail_use_ssl and mail_use_tls:
                client.starttls()
            if mail_username:
                client.login(mail_username, mail_password)
            client.send_message(message)
        return {'ok': True, 'delivery': 'smtp'}
    except Exception as exc:
        app.logger.exception('Falha ao enviar e-mail para %s: %s', to_address, exc)
        return {'ok': False, 'reason': 'send_failed', 'error': str(exc)}

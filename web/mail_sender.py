"""
mail_sender.py — отправка обычных писем + коды подтверждения Google-логина
"""

import logging
import smtplib
import secrets
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTPException

from config import (
    EMAIL_FROM,
    EMAIL_PASSWORD,
    SMTP_SERVER,
    SMTP_PORT,
)

# CRUD-helpers из db.py
from db import (
    save_google_code,
    get_google_code,
    delete_google_code,
)


# ─────────────────────────────────────────────
#  Базовая утилита для отправки письма
# ─────────────────────────────────────────────
def send_email(
    subject: str,
    body: str,
    to_email: str,
    from_email: str = EMAIL_FROM,
    password: str = EMAIL_PASSWORD,
) -> None:
    """
    Отправляет простое текстовое письмо через SMTP.
    """
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        with server:
            server.ehlo()
            if SMTP_PORT != 465:
                server.starttls()
            server.login(from_email, password)
            server.send_message(msg)
            logging.info("Email sent to %s", to_email)
    except SMTPException as e:
        logging.error("SMTP error while sending email to %s: %s", to_email, e)
    except Exception as e:
        logging.error("Unexpected error sending email to %s: %s", to_email, e)


# ─────────────────────────────────────────────
#  Google-login: код подтверждения
# ─────────────────────────────────────────────
async def send_confirmation_code(email: str) -> None:
    """
    Генерирует 6-значный код, сохраняет/обновляет его в БД
    и шлёт письмо пользователю.
    """
    code = f"{secrets.randbelow(10**6):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    # сохраняем в таблицу google_email_confirmations
    await save_google_code(email=email, code=code, expires_at=expires_at)

    subject = "Код подтверждения входа в Luch Neuro"
    body = (
        f"Ваш код подтверждения: {code}\n"
        "Он действует 15 минут.\n\n"
        "Если это были не вы — просто проигнорируйте письмо."
    )
    try:
        send_email(subject, body, email)
    except Exception as e:
        logging.error("Не удалось отправить код подтверждения на %s: %s", email, e)


async def verify_code(email: str, code: str) -> bool:
    """
    Проверяет введённый пользователем код.
    True  → код верный и не просрочен (запись удаляется).
    False → неверный или истёк.
    """
    rec = await get_google_code(email=email)
    if rec is None:
        return False

    saved_code, expires_at = rec
    # Приводим expires_at к aware-дате (UTC), если tzinfo отсутствует
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    # Сравниваем с текущим временем в UTC
    if code != saved_code or expires_at < datetime.now(timezone.utc):
        return False

    # подтверждён — удаляем, чтобы код нельзя было использовать повторно
    await delete_google_code(email)
    return True
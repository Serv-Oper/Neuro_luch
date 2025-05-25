# web/auth.py
"""
Регистрация, аутентификация и JWT-токены для Luch Neuro Web.
Поддерживается:
 - email+пароль + подтверждение кода
 - гостевой доступ с ограничением запросов
 - вход через Google (OIDC)
Зависимости: passlib[bcrypt], python-jose[cryptography], google-auth
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
import asyncio
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.auth.exceptions import GoogleAuthError
from jose import jwt, JWTError
from passlib.context import CryptContext

# Для отправки писем
from web.mail_sender import send_email
from config import (
    JWT_SECRET_KEY,       # теперь используем как SECRET_KEY для JWT
    EMAIL_FROM,           # e-mail отправителя
    EMAIL_PASSWORD,       # пароль SMTP
    CONFIRM_CODE_EXP_MIN, # время жизни кода (в минутах)
    GOOGLE_CLIENT_ID,     # client ID для проверки audience
)

# DB-слой
from db import (
    create_user,
    verify_user_password,
    create_confirmation_code,
    verify_confirmation_code,
    is_email_confirmed,
    create_guest_session,
    get_guest_session,
    increment_guest_request,
    get_user_by_google_id,
    create_google_account,
)

# ─────────── Настройки JWT ───────────
SECRET_KEY = JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# ─────────── Контекст для хэшей паролей ───────────
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─────────── Утилиты ───────────
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _generate_confirmation_code(length: int = 6) -> str:
    alphabet = string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ─────────── Регистрация по e-mail + пароль ───────────
async def register_user(email: str, password: str) -> None:
    """
    Шаг 1: принимаем email+пароль, создаём временный User (без активации),
    генерируем 6-значный код, сохраняем его и отправляем письмо.
    """
    # 1) Создаём пользователя (password_hash сохраняется)
    pwd_hash = _pwd_ctx.hash(password)
    await create_user(email=email, password_hash=pwd_hash)

    # 2) Генерируем и сохраняем код подтверждения
    code = _generate_confirmation_code()
    expires_at = _now_utc() + timedelta(minutes=CONFIRM_CODE_EXP_MIN)
    await create_confirmation_code(user_email=email, code=code, expires_at=expires_at)

    # 3) Отправляем код на почту
    subject = "Ваш код подтверждения Luch Neuro"
    body = (
        f"Здравствуйте!\n\n"
        f"Ваш код подтверждения в Luch Neuro: {code}\n"
        f"Он действителен {CONFIRM_CODE_EXP_MIN} минут.\n\n"
        "Если вы не запрашивали регистрацию — просто проигнорируйте это письмо."
    )
    # Асинхронная отправка письма в отдельном потоке, чтобы не блокировать event-loop
    await asyncio.to_thread(
        send_email,
        subject,
        body,
        email,
        EMAIL_FROM,
        EMAIL_PASSWORD,
    )


async def confirm_user_email(email: str, code: str) -> bool:
    return await verify_confirmation_code(user_email=email, code=code)

async def is_user_email_confirmed(email: str) -> bool:
    """
    Возвращает True, если для этого email уже есть запись
    EmailConfirmationCode.confirmed == True.
    """
    return await is_email_confirmed(user_email=email)


# ─────────── Аутентификация email+пароль ───────────
async def authenticate_user(email: str, password: str) -> bool:
    """
    1) Проверяем, что пользователь есть и пароль верный;
    2) Проверяем, что email уже подтверждён (есть confirmed=True).
    """
    # 1) проверяем пароль
    ok = await verify_user_password(email=email, plain_password=password)
    if not ok:
        return False

    # 2) проверяем флаг confirmed
    return await is_user_email_confirmed(email)


logger = logging.getLogger(__name__)


# ─────────── Google OAuth (OIDC) ───────────
async def authenticate_google(id_token_str: str) -> Optional[str]:
    """
    Декодируем и проверяем id_token от Google.
    Возвращаем email пользователя и привязываем к нашей БД.
    """
    try:
        info = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            audience=GOOGLE_CLIENT_ID
        )
        email = info.get("email")
        google_id = info.get("sub")
        name = info.get("name")
    except (ValueError, GoogleAuthError) as e:
        logger.error(f"Google token verification failed: {e}")
        return None

    if not email or not google_id:
        return None

    # 1) пытаемся найти существующего пользователя по google_id
    user = await get_user_by_google_id(google_id)
    if user is None:
        # 2) или создаём нового пользователя и привязываем к нему Google-аккаунт
        user = await create_user(email=email, password_hash=None)
        await create_google_account(
            user_id=user.id,
            google_id=google_id,
            email=email,
            name=name,
        )

    return email


# ─────────── Гостевой доступ ───────────
async def create_guest_token() -> str:
    """
    Генерим уникальный токен для гостя, сохраняем сессию и возвращаем JWT.
    """
    token = secrets.token_urlsafe(32)
    await create_guest_session(session_token=token)
    # JWT с подом = токен гостя
    return create_access_token(sub=token, expires_minutes=ACCESS_TOKEN_EXPIRE_MINUTES)


async def verify_guest_token(sub: str) -> bool:
    """
    Проверяем, что сессия гостя существует и не исчерпала лимит.
    """
    gs = await get_guest_session(session_token=sub)
    if not gs:
        return False
    # инкрементируем счётчик; если >3 — блокируем
    cnt = await increment_guest_request(session_token=sub)
    return cnt <= 3


# ─────────── JWT ───────────
def create_access_token(sub: str, expires_minutes: Optional[int] = None) -> str:
    """
    Генерирует JWT с полем 'sub' (email или guest-token) и временем жизни.
    """
    exp = _now_utc() + timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": sub, "exp": exp}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def decode_token(token: str) -> Optional[str]:
    """
    Декодирует JWT, возвращает поле 'sub' (string) или None при ошибке.
    """
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return data.get("sub")
    except JWTError:
        return None
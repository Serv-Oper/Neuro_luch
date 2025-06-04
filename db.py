"""
db.py – асинхронный слой данных проекта Luch_Neuro
Author: senior-dev

Зависимости:
    pip install sqlalchemy==2.0.29 aiomysql
"""
from __future__ import annotations

import enum
from passlib.context import CryptContext
from contextlib import asynccontextmanager
from datetime import datetime, date, timezone
from typing import List
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    select,
    update,
    func,
    delete,
)
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.engine import URL
from sqlalchemy.dialects.mysql import insert as mysql_insert

# Maximum verification attempts for email confirmation codes
MAX_CONFIRM_CODE_ATTEMPTS = 5

# ──────────────────────────────────────────────────
#  Async engine & sessionmaker
# ──────────────────────────────────────────────────

def _build_db_url() -> URL:
    """Build database URL from environment variables."""
    from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME  # lazy import

    # Используем TCP даже если в .env указано localhost
    host = DB_HOST if DB_HOST else "127.0.0.1"
    if host == "localhost":
        host = "127.0.0.1"

    return URL.create(
        drivername="mysql+aiomysql",
        username=DB_USER,
        password=DB_PASSWORD,
        host=host,
        port=int(DB_PORT),
        database=DB_NAME,
        query={"charset": "utf8mb4"},
    )

# Строим URL
URL_DSN = _build_db_url()

# Создаём асинхронный движок
ENGINE: AsyncEngine = create_async_engine(
    URL_DSN,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

# Создаём сессию
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    ENGINE, expire_on_commit=False
)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Контекстный менеджер для быстрой работы с сессией."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def with_session(fn):
    """Decorator: автоматически создаёт / коммитит сессию, если не передана вручную."""

    async def wrapper(*args, session: AsyncSession | None = None, **kwargs):
        if session is not None:
            return await fn(*args, session=session, **kwargs)
        async with get_session() as s:
            return await fn(*args, session=s, **kwargs)

    return wrapper


# ──────────────── RESET TODAY USAGE ────────────────
@with_session
async def reset_today_usage(user_id: int, session: AsyncSession | None = None) -> None:
    """
    Удаляем все записи использования (usage) текущего дня для данного пользователя.
    """
    from datetime import date

    today = date.today()
    stmt = delete(Usage).where(
        Usage.user_id == user_id,
        Usage.date == today
    )
    await session.execute(stmt)


# ─────────────────────────────
#  Declarative models
# ─────────────────────────────
class Base(AsyncAttrs, DeclarativeBase):
    pass

class SubscriptionStatus(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"

class MessageRole(str, enum.Enum):
    USER = "user"
    BOT = "bot"

from sqlalchemy import BigInteger, UniqueConstraint, Index

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email:           Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    password_hash:   Mapped[str | None] = mapped_column(String(128), nullable=True)
    registered_at:        Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    subscription_status:  Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.FREE, nullable=False
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    default_model_key:    Mapped[str]   = mapped_column(String(32), default="fast")
    is_admin:             Mapped[bool]  = mapped_column(Boolean, default=False, nullable=False)
    timezone:             Mapped[str]   = mapped_column(String(32), default="UTC", nullable=False)

    telegram_accounts: Mapped[list["TelegramAccount"]] = relationship(
        back_populates="user", cascade="all,delete"
    )
    google_accounts:   Mapped[list["GoogleAccount"]]   = relationship(
        back_populates="user", cascade="all,delete"
    )
    chats:            Mapped[list["Chat"]]         = relationship(
        back_populates="user", cascade="all,delete"
    )
    subscriptions:    Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all,delete"
    )
    usage_rows:       Mapped[list["Usage"]]        = relationship(
        back_populates="user", cascade="all,delete"
    )

class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("telegram_id", name="uix_tg_account_telegram_id"),
        Index("ix_tg_account_user_telegram", "user_id", "telegram_id"),
    )

    user: Mapped["User"] = relationship(
        back_populates="telegram_accounts", cascade="all,delete"
    )

class GoogleAccount(Base):
    __tablename__ = "google_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    google_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="google_accounts")


class EmailConfirmationCode(Base):
    __tablename__ = "email_confirmation_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_email: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_email", "code", name="uix_email_code"),
    )

class GuestSession(Base):
    __tablename__ = "guest_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # убрали связь с User

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plan: Mapped[str] = mapped_column(String(32))
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("active", "expired", name="subscription_state"), nullable=False
    )
    payment_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="subscriptions")


class Model(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    model_id: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    visible_for_free: Mapped[bool] = mapped_column(Boolean, default=False)

class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    model_key: Mapped[str] = mapped_column(String(32), default="fast", nullable=False)
    title: Mapped[str | None] = mapped_column(String(28))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_interaction_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        # Простой индекс по user_id и is_active для быстрого поиска
        Index("ix_user_active", "user_id", "is_active"),
    )

    user: Mapped["User"] = relationship(back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="chat", cascade="all,delete"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # общее количество токенов (оставляем для обратной совместимости)
    token_count: Mapped[int | None] = mapped_column(Integer)

    # NEW - раздельный учёт токенов
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)

    chat: Mapped["Chat"] = relationship(back_populates="messages")


class Usage(Base):
    __tablename__ = "usage"
    __table_args__ = (
        UniqueConstraint("user_id", "date", "model_key", name="uix_user_date_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    model_key: Mapped[str] = mapped_column(String(16))
    count: Mapped[int] = mapped_column(Integer, default=0)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="usage_rows")


# ─────────────────────────────
#  CRUD-операции
# ─────────────────────────────
@with_session
async def finish_chat(
    chat_id: int,
    title: str | None = None,
    session: AsyncSession | None = None,
) -> None:
    stmt = update(Chat).where(
        Chat.id == chat_id,
        Chat.is_active.is_(True)
    ).values(is_active=False)
    if title is not None:
        stmt = stmt.values(title=title[:28])
    await session.execute(stmt)
    await session.flush()

@with_session
async def delete_chat(
    chat_id: int,
    session: AsyncSession | None = None,
) -> None:
    """
    Полностью удаляет чат и все связанные с ним сообщения из БД.
    """
    await session.execute(
        delete(Chat)
        .where(Chat.id == chat_id)
    )

@with_session
async def get_or_create_user(
    *,
    telegram_id: int | None = None,
    email: str | None = None,
    username: str | None = None,
    session: AsyncSession | None = None,
) -> User:
    user: User | None = None

    # 1) Если есть привязанный TelegramAccount — берём его пользователя
    if telegram_id is not None:
        ta = await session.scalar(
            select(TelegramAccount).where(TelegramAccount.telegram_id == telegram_id)
        )
        if ta:
            # вместо ta.user — делаем явный асинхронный запрос
            user = await session.scalar(
                select(User).where(User.id == ta.user_id)
            )

    # 2) Если не найден по Telegram, пробуем по email
    if user is None and email is not None:
        user = await session.scalar(select(User).where(User.email == email))

    # 3) Если нашли пользователя — обновляем/добавляем TelegramAccount и возвращаем
    if user:
        if telegram_id is not None:
            stmt = mysql_insert(TelegramAccount).values(
                user_id=int(user.id),
                telegram_id=telegram_id,
                username=username,
                created_at=datetime.now(timezone.utc),
            ).on_duplicate_key_update(username=username)
            await session.execute(stmt)
        return user

    # 4) Ни по чему не нашли — создаём нового пользователя и TelegramAccount
    user = User(email=email, password_hash=None)
    session.add(user)
    await session.flush()
    if telegram_id is not None:
        stmt = mysql_insert(TelegramAccount).values(
            user_id=user.id,
            telegram_id=telegram_id,
            username=username,
            created_at=datetime.now(timezone.utc),
        )
        await session.execute(stmt)
    return user


@with_session
async def get_model_by_key(
    key_name: str, session: AsyncSession | None = None
) -> Model | None:
    return await session.scalar(
        select(Model).where(Model.key_name == key_name, Model.is_active.is_(True))
    )


@with_session
async def create_chat(
    user_id: int,
    model_key: str,
    session: AsyncSession | None = None,
) -> Chat:
    # Сбрасываем другие активные чаты
    await session.execute(
        update(Chat)
        .where(Chat.user_id == user_id, Chat.is_active.is_(True))
        .values(is_active=False)
    )
    chat = Chat(user_id=user_id, model_key=model_key, is_active=True)
    session.add(chat)
    await session.flush()
    return chat

@with_session
async def set_active_chat(
    user_id: int,
    chat_id: int,
    model_key: str | None = None,
    session: AsyncSession | None = None,
) -> Chat:
    """
    Помечает указанный чат активным для пользователя,
    сбрасывает все остальные и возвращает экземпляр Chat.
    """
    # 1) Сброс всех активных чатов
    await session.execute(
        update(Chat)
        .where(Chat.user_id == user_id, Chat.is_active.is_(True))
        .values(is_active=False)
    )

    # 2) Активация нужного, при желании обновляем model_key
    values: dict[str, object] = {"is_active": True}
    if model_key is not None:
        values["model_key"] = model_key

    await session.execute(
        update(Chat)
        .where(Chat.id == chat_id)
        .values(**values)
    )

    # 3) Flush + получение свежего объекта
    await session.flush()
    chat_obj = await session.scalar(
        select(Chat).where(Chat.id == chat_id)
    )
    if chat_obj is None:
        raise ValueError(f"Chat with id={chat_id} not found")
    return chat_obj


@with_session
async def get_active_chat(
    user_id: int, session: AsyncSession | None = None
) -> Chat | None:
    return await session.scalar(
        select(Chat).where(Chat.user_id == user_id, Chat.is_active.is_(True))
    )

@with_session
async def get_google_account_by_email(
    email: str,
    session: AsyncSession | None = None
) -> GoogleAccount | None:
    """
    Возвращает запись GoogleAccount по полю email, или None.
    """
    return await session.scalar(
        select(GoogleAccount).where(GoogleAccount.email == email)
    )

@with_session
async def get_user_chats(
    user_id: int, limit: int = 20, session: AsyncSession | None = None
) -> List[Chat]:
    """
    Возвращает до `limit` последних чатов пользователя,
    отсортированных по времени последнего взаимодействия.
    """
    result = await session.scalars(
        select(Chat)
        .where(Chat.user_id == user_id)
        .order_by(Chat.last_interaction_at.desc())  # ← теперь по активности
        .limit(limit)
    )
    return list(result.all())

@with_session
async def seed_models(models: dict[str, str], session: AsyncSession | None = None) -> None:
    """
    Загружает или обновляет записи в таблице models по переданному словарю key_name → model_id.
    При конфликте по полю key_name (UNIQUE) обновляет model_id.
    """
    for key_name, model_id in models.items():
        stmt = (
            mysql_insert(Model)  # <-- передаём именно модель, а не Model.__table__
            .values(
                key_name=key_name,
                model_id=model_id,
                description=None,
                is_active=True,
                visible_for_free=(key_name == "fast"),
            )
            .on_duplicate_key_update(
                model_id=model_id
            )
        )
        await session.execute(stmt)

@with_session
async def add_message(
    chat_id: int,
    role: MessageRole,
    content: str,
    *,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    session: AsyncSession | None = None,
) -> Message:
    msg = Message(
        chat_id=chat_id,
        role=role,
        content=content,
        token_count=total_tokens or prompt_tokens or completion_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    session.add(msg)
    await session.flush()
    # обновление времени последнего взаимодействия
    await session.execute(
        update(Chat)
        .where(Chat.id == chat_id)
        .values(last_interaction_at=datetime.now(timezone.utc))
    )
    return msg


@with_session
async def get_chat_messages(
    chat_id: int, limit: int = 50, session: AsyncSession | None = None
) -> List[Message]:
    result = await session.scalars(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.timestamp.asc())
        .limit(limit)
    )
    # Приводим к list, чтобы действительно получить List[Message]
    messages: list[Message] = list(result.all())
    # вернуть последние N сообщений в хронологическом порядке
    return messages[-limit:]

# ──────────────── NEW FUNCTION ────────────────
@with_session
async def get_messages_for_chat(
    chat_id: int,
    session: AsyncSession | None = None,
) -> List[Message]:
    """
    Возвращает все сообщения указанного чата в хронологическом порядке (от старых к новым).
    """
    result = await session.scalars(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.timestamp.asc())
    )
    return list(result.all())

# ──────────────── LIMITED MESSAGES FOR CHAT ────────────────
@with_session
async def get_last_limited_messages(
    chat_id: int,
    max_user: int = 120,
    max_bot: int = 120,
    session: AsyncSession | None = None,
) -> List[Message]:
    """
    Возвращает до 120 самых новых сообщений от USER и до 120 самых новых сообщений от BOT
    для данного чата, объединяет их и возвращает в хронологическом порядке.
    """
    # 1) Получаем до max_user последних USER-сообщений (сортировка по убыванию времени)
    user_rs = await session.scalars(
        select(Message)
        .where(Message.chat_id == chat_id, Message.role == MessageRole.USER)
        .order_by(Message.timestamp.desc())
        .limit(max_user)
    )
    user_msgs = list(user_rs.all())

    # 2) Получаем до max_bot последних BOT-сообщений
    bot_rs = await session.scalars(
        select(Message)
        .where(Message.chat_id == chat_id, Message.role == MessageRole.BOT)
        .order_by(Message.timestamp.desc())
        .limit(max_bot)
    )
    bot_msgs = list(bot_rs.all())

    # 3) Объединяем и сортируем всё по возрастанию времени (от старых к новым)
    combined = user_msgs + bot_msgs
    combined.sort(key=lambda m: m.timestamp)
    return combined

# ──────────────── USER MESSAGE COUNT ────────────────
@with_session
async def get_user_message_count(
    chat_id: int,
    session: AsyncSession | None = None
) -> int:
    """
    Возвращает количество сообщений с ролью USER в данном чате.
    """
    cnt = await session.scalar(
        select(func.count(Message.id))
        .where(Message.chat_id == chat_id, Message.role == MessageRole.USER)
    )
    return cnt or 0

# ─────────── после
@with_session
async def increment_usage(
    user_id: int,
    today: date,
    *,
    model_key: str,
    session: AsyncSession | None = None
) -> int:
    """
    Атомарно увеличиваем счётчик usage по user_id, date и model_key.
    """
    stmt = (
        mysql_insert(Usage)
        .values(user_id=user_id, date=today, model_key=model_key, count=1)
        .on_duplicate_key_update(count=Usage.count + 1)
    )
    await session.execute(stmt)
    new_cnt = await session.scalar(
        select(Usage.count).where(
            Usage.user_id == user_id,
            Usage.date == today,
            Usage.model_key == model_key,
        )
    )
    return new_cnt or 1


@with_session
async def get_today_usage(
    user_id: int,
    today: date,
    *,
    model_key: str,
    session: AsyncSession | None = None
) -> int:
    """
    Возвращает текущий счётчик usage по user_id, date и model_key.
    """
    row = await session.scalar(
        select(Usage.count).where(
            Usage.user_id == user_id,
            Usage.date == today,
            Usage.model_key == model_key,
        )
    )
    return row or 0

@with_session
async def get_today_total_usage(
    user_id: int,
    today: date,
    session: AsyncSession | None = None
) -> int:
    """
    Суммарное число запросов пользователя за today — всех моделей вместе.
    """
    row = await session.scalar(
        select(func.coalesce(func.sum(Usage.count), 0))
        .where(Usage.user_id == user_id, Usage.date == today)
    )
    return row or 0

@with_session
async def update_chat_model(
    chat_id: int,
    new_model_key: str,
    session: AsyncSession | None = None
) -> None:
    """
    Меняет модель у существующего чата.
    """
    await session.execute(
        update(Chat)
        .where(Chat.id == chat_id)
        .values(model_key=new_model_key)
    )

# ─────────────────────────────
#  CRUD для GoogleAccount
# ─────────────────────────────
@with_session
async def create_google_account(
    user_id: int,
    google_id: str,
    email: str | None = None,
    name: str | None = None,
    session: AsyncSession | None = None,
) -> GoogleAccount:
    ga = GoogleAccount(
        user_id=user_id,
        google_id=google_id,
        email=email,
        name=name,
    )
    session.add(ga)
    await session.flush()
    return ga


@with_session
async def get_user_by_google_id(
    google_id: str, session: AsyncSession | None = None
) -> User | None:
    ga_user_id = await session.scalar(
        select(GoogleAccount.user_id).where(GoogleAccount.google_id == google_id)
    )
    if ga_user_id is None:
        return None
    return await session.scalar(
        select(User).where(User.id == ga_user_id)
    )

# ─────────────────────────────────────────────
#  ORM model for Google email confirmation codes
# ─────────────────────────────────────────────
class GoogleEmailConfirmationCode(Base):
    __tablename__ = "google_email_confirmations"

    email: Mapped[str] = mapped_column(String(128), primary_key=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

# ─────────────────────────────────────────────
#  CRUD for GoogleEmailConfirmationCode
# ─────────────────────────────────────────────
@with_session
async def save_google_code(
    email: str,
    code: str,
    expires_at: datetime,
    session: AsyncSession | None = None
) -> None:
    """
    Save or update a Google email confirmation code with expiration.
    """
    stmt = mysql_insert(GoogleEmailConfirmationCode).values(
        email=email,
        code=code,
        expires_at=expires_at,
    ).on_duplicate_key_update(
        code=code,
        expires_at=expires_at,
    )
    await session.execute(stmt)

@with_session
async def get_google_code(
    email: str,
    session: AsyncSession | None = None
) -> tuple[str, datetime] | None:
    """
    Retrieve the (code, expires_at) tuple for a given email, or None if not found.
    """
    ecc = await session.scalar(
        select(GoogleEmailConfirmationCode).where(GoogleEmailConfirmationCode.email == email)
    )
    if not ecc:
        return None
    return ecc.code, ecc.expires_at

@with_session
async def delete_google_code(
    email: str,
    session: AsyncSession | None = None
) -> None:
    """
    Delete the confirmation code record for the given email.
    """
    await session.execute(
        delete(GoogleEmailConfirmationCode).where(GoogleEmailConfirmationCode.email == email)
    )


# ─────────────────────────────
#  CRUD для EmailConfirmationCode
# ─────────────────────────────
@with_session
async def create_confirmation_code(
    user_email: str,
    code: str,
    expires_at: datetime,
    session: AsyncSession | None = None,
) -> EmailConfirmationCode:
    ecc = EmailConfirmationCode(
        user_email=user_email,
        code=code,
        expires_at=expires_at,
        attempts=0,
    )
    session.add(ecc)
    await session.flush()
    return ecc

@with_session
async def update_chat_title(chat_id: int, title: str, session: AsyncSession | None = None) -> None:
    await session.execute(
        update(Chat)
        .where(Chat.id == chat_id)
        .values(title=title, last_interaction_at=datetime.now(timezone.utc))
    )

@with_session
async def verify_confirmation_code(
    user_email: str,
    code: str,
    session: AsyncSession | None = None,
) -> bool:
    """
    Проверяет последний отправленный код для email,
    сравнивая в UTC-aware формате.
    """
    now_aware = datetime.now(timezone.utc)

    ecc = await session.scalar(
        select(EmailConfirmationCode)
        .where(EmailConfirmationCode.user_email == user_email)
        .order_by(EmailConfirmationCode.created_at.desc())
        .limit(1)
    )
    if not ecc:
        return False

    # Неправильный код
    if ecc.code != code:
        await session.execute(
            update(EmailConfirmationCode)
            .where(EmailConfirmationCode.id == ecc.id)
            .values(attempts=EmailConfirmationCode.attempts + 1)
        )
        return False

    # Делаем expires_at timezone-aware, если нужно
    exp_at = ecc.expires_at
    if exp_at.tzinfo is None:
        exp_at = exp_at.replace(tzinfo=timezone.utc)

    # Просрочен или уже подтверждён
    if exp_at < now_aware or ecc.confirmed:
        await session.execute(
            update(EmailConfirmationCode)
            .where(EmailConfirmationCode.id == ecc.id)
            .values(attempts=EmailConfirmationCode.attempts + 1)
        )
        return False

    # Слишком много попыток
    if ecc.attempts >= MAX_CONFIRM_CODE_ATTEMPTS:
        return False

    # Всё ок — отмечаем подтверждённым
    await session.execute(
        update(EmailConfirmationCode)
        .where(EmailConfirmationCode.id == ecc.id)
        .values(confirmed=True)
    )
    await session.flush()
    return True


# ─────────────────────────────
#  CRUD для GuestSession
# ─────────────────────────────
@with_session
async def create_guest_session(
    session_token: str,
    user_id: int | None = None,
    session: AsyncSession | None = None,
) -> GuestSession:
    gs = GuestSession(
        session_token=session_token,
        telegram_id=user_id,
    )
    session.add(gs)
    await session.flush()
    return gs

@with_session
async def get_guest_session(
    session_token: str, session: AsyncSession | None = None
) -> GuestSession | None:
    return await session.scalar(
        select(GuestSession).where(GuestSession.session_token == session_token)
    )

@with_session
async def increment_guest_request(
    session_token: str, session: AsyncSession | None = None
) -> int:
    """
    Атомарно инкрементируем request_count и обновляем last_request_at
    через INSERT … ON DUPLICATE KEY UPDATE, чтобы избежать гонок.
    """
    from datetime import datetime, timezone

    # Попытка вставить новую сессию или обновить существующую за один запрос
    stmt = (
        mysql_insert(GuestSession)
        .values(
            session_token=session_token,
            request_count=1,
            last_request_at=datetime.now(timezone.utc)
        )
        .on_duplicate_key_update(
            request_count=GuestSession.request_count + 1,
            last_request_at=datetime.now(timezone.utc)
        )
    )
    await session.execute(stmt)

    # Забираем и возвращаем актуальное значение счётчика
    new_count = await session.scalar(
        select(GuestSession.request_count)
        .where(GuestSession.session_token == session_token)
    )
    return new_count or 0

@with_session
async def create_user(
    email: str,
    password_hash: str | None,
    session: AsyncSession | None = None
) -> User:
    """
    Создаёт нового пользователя с email и (опциональным) хэшем пароля.
    """
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    await session.flush()
    return user

@with_session
async def get_user_by_email(
    email: str,
    session: AsyncSession | None = None
) -> User | None:
    """
    Возвращает User по exact-email или None.
    """
    return await session.scalar(
        select(User).where(User.email == email)
    )

# создаём единственный CryptContext для всего модуля
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ──────────── ПОСЛЕ ────────────
@with_session
async def get_user_by_telegram_id(
    telegram_id: int,
    session: AsyncSession | None = None
) -> User | None:
    """
    Возвращает User по telegram_id через таблицу telegram_accounts или None.
    """
    ta = await session.scalar(
        select(TelegramAccount.user_id).where(TelegramAccount.telegram_id == telegram_id)
    )
    if ta is None:
        return None
    return await session.scalar(select(User).where(User.id == ta))

@with_session
async def verify_user_password(
    email: str,
    plain_password: str,
    session: AsyncSession | None = None
) -> bool:
    """
    Проверяет, что у пользователя с данным email есть пароль и
    что plain_password соответствует сохранённому хэшу.
    """
    user = await get_user_by_email(email, session=session)
    pwd_hash: str | None = user.password_hash if user else None
    if not pwd_hash:
        return False
    return _pwd_ctx.verify(plain_password, pwd_hash)


# ──────────────────────────────────────────────
#  Guest‑helper: возвращаем ровно одну сессию на user_id
# ──────────────────────────────────────────────
@with_session
async def get_or_create_guest_session(
    user_id: int,
    session: AsyncSession | None = None
) -> GuestSession:
    gs = await session.scalar(
        select(GuestSession).where(GuestSession.telegram_id == user_id)
    )
    if gs:
        return gs

    import secrets
    from datetime import datetime, timezone

    gs = GuestSession(
        session_token=secrets.token_urlsafe(32),
        telegram_id=user_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(gs)
    await session.flush()
    return gs

@with_session
async def bind_telegram(
    user_id: int,
    telegram_id: int,
    username: str | None = None,
    session: AsyncSession | None = None,
) -> TelegramAccount:
    """
    Привязывает Telegram-аккаунт к User. Если уже есть — обновляет username.
    """
    stmt = mysql_insert(TelegramAccount).values(
        user_id=user_id,
        telegram_id=telegram_id,
        username=username,
        created_at=datetime.now(timezone.utc),
    ).on_duplicate_key_update(
        username=username,
    )
    await session.execute(stmt)
    return await session.scalar(
        select(TelegramAccount).where(TelegramAccount.telegram_id == telegram_id)
    )


@with_session
async def unbind_telegram(
    telegram_id: int,
    session: AsyncSession | None = None,
) -> None:
    """
    Удаляет запись в telegram_accounts, отвязывая аккаунт.
    """
    await session.execute(
        delete(TelegramAccount).where(
            TelegramAccount.telegram_id == telegram_id
        )
    )


# Количество привязанных Telegram-аккаунтов для пользователя
@with_session
async def count_telegram_accounts(
    user_id: int,
    telegram_id: int | None = None,
    session: AsyncSession | None = None,
) -> int:
    """
    Возвращает количество привязанных Telegram-аккаунтов для пользователя.
    Если передан telegram_id, считает только для этого telegram_id.
    """
    stmt = select(func.count(TelegramAccount.id)).where(
        TelegramAccount.user_id == user_id
    )
    if telegram_id is not None:
        stmt = stmt.where(TelegramAccount.telegram_id == telegram_id)
    return await session.scalar(stmt) or 0

@with_session
async def is_email_confirmed(user_email: str, session: AsyncSession = None) -> bool:
    rec = await session.scalar(
        select(EmailConfirmationCode)
        .where(
            EmailConfirmationCode.user_email == user_email,
            EmailConfirmationCode.confirmed == True,
        )
        .limit(1)
    )
    return rec is not None

# ─────────────────────────────
#  Инициализация БД (alembic optional)
# ─────────────────────────────
async def init_models(drop_existing: bool = False) -> None:
    """
    Быстрый helper для dev-окружения:
    drop_existing=True удалит все таблицы.
    В production лучше использовать alembic!
    """
    async with ENGINE.begin() as conn:
        if drop_existing:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
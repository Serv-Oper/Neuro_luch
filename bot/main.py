"""
main.py — точка входа для запуска бота Luch_Neuro с продвинутым логированием
"""

import asyncio
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import BOT_TOKEN
from db import init_models, seed_models, ENGINE
from bot.handlers import router, service

from pathlib import Path
from datetime import datetime
from contextlib import suppress

# Путь к папке uploads в корне проекта
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads"
# Интервал очистки (секунды) и время жизни файлов (секунды)
CLEANUP_INTERVAL = 240
FILE_TTL = 300

async def _cleanup_uploads_loop():
    """Удаляет файлы из UPLOADS_DIR старше FILE_TTL каждые CLEANUP_INTERVAL."""
    while True:
        now_ts = datetime.now().timestamp()
        # если папки нет — ждём и повторяем
        if not UPLOADS_DIR.exists():
            await asyncio.sleep(CLEANUP_INTERVAL)
            continue

        for fname in os.listdir(UPLOADS_DIR):
            file_path = UPLOADS_DIR / fname
            if not file_path.is_file():
                continue
            if now_ts - file_path.stat().st_mtime > FILE_TTL:
                with suppress(Exception):
                    file_path.unlink()
        await asyncio.sleep(CLEANUP_INTERVAL)

# ──────────────────────────────────────────────────────────────────────────────
#  1) Глобальная настройка логирования
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)5s | %(name)15s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("aiogram").setLevel(logging.DEBUG)
logging.getLogger("aiohttp").setLevel(logging.DEBUG)

# ──────────────────────────────────────────────────────────────────────────────
#  2) Кастомная сессия для логирования исходящих API-вызовов
# ──────────────────────────────────────────────────────────────────────────────
class SendLoggingSession(AiohttpSession):
    # noinspection PyUnresolvedReferences
    async def request(self, method: str, url: str, **kwargs):
        """
        Логируем каждый исходящий HTTP-запрос к Telegram API,
        а затем — статус и тело ответа.
        """
        logger.debug(
            "→ API call: %s %s | params=%s json=%s",
            method, url, kwargs.get("params"), kwargs.get("json"),
        )
        resp = await super().request(method, url, **kwargs)
        try:
            body = await resp.text()
            logger.debug("← API response: status=%s body=%s", resp.status, body)
        except (aiohttp.ClientError, UnicodeDecodeError) as e:
            # Не удалось прочитать тело — просто логируем статус
            logger.debug("← API response: status=%s (no body): %s", resp.status, e)
        return resp

# ──────────────────────────────────────────────────────────────────────────────
#  3) Middleware для логирования входящих Update
# ──────────────────────────────────────────────────────────────────────────────
from aiogram.types import Update

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        # 1) Если это "сырой" Update — разбираем его
        if isinstance(event, Update):
            if event.message:
                msg = event.message
                info = f"MSG  from={msg.from_user.id} text={msg.text!r}"
            elif event.callback_query:
                cb = event.callback_query
                info = f"CBQ  from={cb.from_user.id} data={cb.data!r}"
            else:
                info = f"OTHER Update (no message or callback)"
        # 2) На всякий случай, если всё же пришёл прямо Message/CallbackQuery
        elif isinstance(event, Message):
            info = f"MSG  from={event.from_user.id} text={event.text!r}"
        elif isinstance(event, CallbackQuery):
            info = f"CBQ  from={event.from_user.id} data={event.data!r}"
        else:
            info = type(event).__name__

        logger.debug(f"← Update: {info}")

        try:
            result = await handler(event, data)
        except Exception:
            logger.exception(f"✖ Exception in handler `{handler.__name__}`")
            raise

        logger.debug(f"→ Handler `{handler.__name__}` completed, result={result!r}")
        return result

# ──────────────────────────────────────────────────────────────────────────────
#  4) Основная функция запуска
# ──────────────────────────────────────────────────────────────────────────────
async def main() -> None:
    # 0) Определяем режим работы и (re)создаём таблицы
    env = os.getenv("ENV", "prod")
    if env == "dev":
        logger.info("DEV mode detected — пересоздаем все таблицы в БД")
        await init_models(drop_existing=True)
    else:
        await init_models(drop_existing=False)

    # 1) Собираем полный список моделей: из API + локальный fallback
    from config import MODELS as LOCAL_MODELS

    logger.info("Fetching models list from IO Intelligence API")
    models_from_api = await service.get_available_models()

    logger.info("Merging with local MODELS fallback")
    for key, mid in LOCAL_MODELS.items():
        models_from_api.setdefault(key, mid)

    # 2) Сидируем все модели в базу
    logger.info("Seeding all models into database")
    await seed_models(models_from_api)

    # 3) Готовим сессию для логирования исходящих HTTP-запросов к Telegram API
    session = SendLoggingSession()

    # 4) Инициализируем Bot с этой сессией
    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
        session=session,
    )

    # 5) Оборачиваем методы отправки, чтобы логировать тексты, которые бот шлёт
    _orig_send = bot.send_message

    async def _logged_send(chat_id, text, **kwargs):
        logger.debug(
            "→ BOT send_message → chat_id=%r text=%r kwargs=%r",
            chat_id, text, kwargs
        )
        return await _orig_send(chat_id, text, **kwargs)

    bot.send_message = _logged_send  # type: ignore

    _orig_edit = bot.edit_message_text

    async def _logged_edit(*, text, chat_id=None, message_id=None, **kwargs):
        logger.debug(
            "→ BOT edit_message_text → chat_id=%r message_id=%r text=%r kwargs=%r",
            chat_id, message_id, text, kwargs
        )
        return await _orig_edit(text=text, chat_id=chat_id, message_id=message_id, **kwargs)

    bot.edit_message_text = _logged_edit  # type: ignore

    # 6) Dispatcher + LoggingMiddleware для входящих Update
    dp = Dispatcher()
    dp.update.middleware(LoggingMiddleware())
    dp.include_router(router)

    # 7) Запускаем polling Telegram-бота и фоновую очистку uploads
    cleanup_task = asyncio.create_task(_cleanup_uploads_loop())

    try:
        logger.info("Старт polling Telegram-бота")
        await dp.start_polling(bot)
    finally:
        # Останавливаем задачу очистки uploads
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task

        # 8) Graceful shutdown
        logger.info("Останавливаем AIService...")
        await service.close()

        logger.info("Закрываем сессию Telegram Bot API...")
        await bot.session.close()

        logger.info("Завершаем соединения с БД...")
        await ENGINE.dispose()

        logger.info("Бот успешно остановлен.")

# ──────────────────────────────────────────────────────────────────────────────
#  Запуск при прямом выполнении
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки, завершение работы.")
# utils.py — общие утилиты и middleware для Luch_Neuro

import logging
from datetime import date
from functools import wraps
from typing import Callable, Any, Awaitable, Tuple, Optional
from aiogram.types import CallbackQuery
from aiogram.types import File
from config import FREE_DAILY_LIMIT, BOT_TOKEN, SUPPORT_USERNAME
from db import SubscriptionStatus
from db import get_today_usage, increment_usage
from bot.keyboards import subscription_keyboard
import re
import html

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────
# Убираем ведущие Markdown‐заголовки (“#”, “##”, …) в начале строк
# ──────────────────────────────────────────────────
def strip_markdown_heads(text: str) -> str:
    """
    Убирает от 1 до 6 символов '#' и любые пробелы после них
    в начале каждой строки.
    """
    return re.sub(r'(?m)^#{1,6}\s*', '', text)


# ──────────────────────────────────────────────────
# Разбить текст на куски длиной ≤4096 символов,
# стараясь не разрывать слова
# ──────────────────────────────────────────────────
def chunk_text(text: str, max_len: int = 4096) -> list[str]:
    """
    Разбивает текст на фрагменты длиной ≤ max_len символов.
    Старательно рвёт по последнему переводу строки или пробелу перед границей,
    чтобы не разрывать слова.
    """
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        if end < len(text):
            sep_n = text.rfind("\n", start, end)
            sep_s = text.rfind(" ", start, end)
            sep = max(sep_n, sep_s)
            if sep > start:
                end = sep
        chunks.append(text[start:end].rstrip())
        start = end
    return chunks


# ────────────────────────────────────────────────────────────────
async def send_final_answer(
    message,
    raw_body: str,
    reply_markup=None
) -> None:
    """
    Шлёт в чат итоговый текст:
      0) Убирает ведущие '#' в начале строк
      1) Преобразует Markdown-подобную разметку в HTML
      2) Разбивает на фрагменты ≤4096 символов
      3) Добавляет заголовок только к первому фрагменту
      4) Прикрепляет reply_markup только к последнему сообщению
    """
    # 0) убираем все ведущие “#” в начале строк
    cleaned = strip_markdown_heads(raw_body)

    # 1) преобразуем
    formatted = format_html(cleaned)

    # 2) разбиваем
    parts = chunk_text(formatted)

    # 3) шлём
    header = "<b>Итоговый ответ:</b>\n"
    for idx, part in enumerate(parts):
        text = header + part if idx == 0 else part
        markup = reply_markup if (reply_markup and idx == len(parts) - 1) else None
        await message.answer(text, parse_mode="HTML", reply_markup=markup)

# —————————————————————————————————————————————————————————————
#  Исключения для централизованной обработки в handlers.py
# —————————————————————————————————————————————————————————————
class LimitExceededError(Exception):
    """Свободный лимит исчерпан."""
    pass


class MissingChatError(Exception):
    """Нет активного чата у пользователя."""
    pass


# —————————————————————————————————————————————————————————————
#  Проверка бесплатного лимита и инкремент
# —————————————————————————————————————————————————————————————
async def check_and_increment_usage(
    user_id: int,
    model_key: str,
    subscription_status: SubscriptionStatus
) -> None:
    """
    Проверить, что пользователь не превысил ежедневный лимит по модели,
    и увеличить счётчик. Лимиты:
      • Free: FREE_DAILY_LIMIT (всех запросов вместе)
      • Premium:
          – fast: 45
          – smart, vision: 15
    """
    today = date.today()

    # 1) Вычисляем лимит по статусу и модели
    if subscription_status == SubscriptionStatus.FREE:
        limit = FREE_DAILY_LIMIT
    else:
        if model_key == "fast":
            limit = 45
        elif model_key in ("smart", "vision"):
            limit = 15
        else:
            # на всякий случай — тот же free-лимит
            limit = FREE_DAILY_LIMIT

    # 2) Считаем текущее число запросов по этой модели
    used = await get_today_usage(user_id, today, model_key=model_key)

    # 3) Проверяем и бросаем, если исчерпано
    if used >= limit:
        raise LimitExceededError(
            f"🔒 Вы израсходовали максимальное количество запросов ({limit}) "
            f"для модели «{model_key}» за сегодня."
        )

    # 4) Инкрементируем счётчик
    await increment_usage(user_id, today, model_key=model_key)


# —————————————————————————————————————————————————————————————
#  Формирование прямой ссылки на сохранённый файл Telegram
# —————————————————————————————————————————————————————————————
def build_telegram_file_url(file: File) -> str:
    """
    Получает объект File от Telegram и возвращает прямой URL
    для доступа к файлу через Bot API.
    """
    return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"


def format_html(raw: str) -> str:
    """
    Преобразует Markdown-подобную разметровку в HTML для Telegram, поддерживая:
      • Заголовки уровня 1–3 (#, ##, ###) → <b>…</b>
      • Жирный+курсив (***…***), жирный (**…**) и курсив (*…*)
      • Подчёркивание (__…__) → <u>…</u>
      • Зачёркивание (~~…~~) → <s>…</s>
      • Inline-код (`…`) → <code>…</code>
      • Блочный код (```…```) → <pre>…</pre>
      • Ссылки [text](https://…) → <a href="…">text</a>
      • Цитаты строк ("> …") → <i>…</i>
      • Маркеры списков ("- " или "* ") → •
      • Нумерованные списки ("1. ") сохраняются
      • Экранирование HTML-спецсимволов
      • Удаление избыточных пустых строк
    """
    # 1) Сначала HTML-escape всего входа
    text = html.escape(raw)

    # 2) Код-блоки: ```…```  — с флагом DOTALL через (?s)
    text = re.sub(
        r'(?s)```(.+?)```',
        lambda m: f'<pre>{html.escape(m.group(1))}</pre>',
        text
    )

    # 3) Inline-код: `…`
    text = re.sub(
        r'`([^`\n]+?)`',
        lambda m: f'<code>{html.escape(m.group(1))}</code>',
        text
    )

    # 4) Ссылки [text](https://...)
    text = re.sub(
        r'\[([^]]+)]\((https?://[^\s)]+)\)',
        r'<a href="\2">\1</a>',
        text
    )

    # 5) Подчёркивание: __…__
    text = re.sub(r'__(.+?)__', r'<u>\1</u>', text)

    # 6) Зачёркивание: ~~…~~
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)

    # 7) Жирный+курсив, жирный, курсив
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*(.+?)\*\*',   r'<b>\1</b>',     text)
    text = re.sub(r'\*(.+?)\*',       r'<i>\1</i>',     text)

    # 8) Заголовки уровней 1–3: # …, ## …, ### …
    #    объединяем в один паттерн: #{1,3}
    text = re.sub(r'(?m)^(#{1,3})\s*(.+)', r'<b>\2</b>', text)

    # 9) Цитаты строк: "> текст"
    text = re.sub(r'(?m)^>\s*(.+)', r'<i>\1</i>', text)

    # 10) Маркированные списки: "-", "*"
    text = re.sub(r'(?m)^[ \t]*[-*]\s+', '• ', text)

    # 11) Нумерованные списки оставляем: "1. ", "2. " и т.д. — HTML-escape уже сделан

    # 12) Удаляем лишние подряд идущие пустые строки (более 2 → 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text

# —————————————————————————————————————————————————————————————
#  Парсер callback_data вида "action:param"
# —————————————————————————————————————————————————————————————
def parse_callback(data: str) -> Tuple[str, Optional[str]]:
    """
    Разбивает callback_data по первому двоеточию.
    Возвращает (action, param) или (data, None).
    """
    if ":" in data:
        action, param = data.split(":", 1)
    else:
        action, param = data, None
    return action, param


# —————————————————————————————————————————————————————————————
#  Декоратор для хэндлеров, чтобы ловить наши исключения
# —————————————————————————————————————————————————————————————
def handle_errors(
    func: Callable[..., Awaitable[Any]]
) -> Callable[..., Awaitable[Any]]:
    """
    Обёртка для хэндлеров, которая:
      - ловит LimitExceededError  → шлёт сообщение юзеру с кнопкой "Купить подписку"
      - ловит MissingChatError    → шлёт подсказку создать чат
      - ловит любые другие ошибки → логирует и шлёт общий алерт
    """
    @wraps(func)
    async def wrapper(update: Any, *args, **kwargs):
        try:
            return await func(update, *args, **kwargs)
        except LimitExceededError as le:
            # для CallbackQuery отвечаем в чате, куда пришёл вызов
            if isinstance(update, CallbackQuery):
                target = update.message
                await update.answer()  # закрываем loading
            else:
                target = update  # Message
            await target.answer(
                str(le),
                reply_markup=subscription_keyboard(False)
            )
        except MissingChatError as mc:
            from keyboards import main_menu_keyboard

            if isinstance(update, CallbackQuery):
                target = update.message
                await update.answer()
            else:
                target = update
            # Только текст ошибки и возвращаем главное меню
            await target.answer(
                str(mc),
                reply_markup=main_menu_keyboard()
            )
        except Exception as e:
            logger.exception("Unhandled error in handler %s: %s", func.__name__, e)
            if isinstance(update, CallbackQuery):
                target = update.message
                await update.answer()
            else:
                target = update
            await target.answer(
                f"⚠️ Произошла непредвиденная ошибка. "
                f"Попробуйте снова или напишите @{SUPPORT_USERNAME}."
            )
    return wrapper
# ────────────────────────────────────────────────────────────────
#  Безопасное закрытие callback — игнорирует «query is too old»
# ────────────────────────────────────────────────────────────────
from aiogram.exceptions import TelegramBadRequest


async def safe_answer(
    callback: CallbackQuery,
    *cb_args,
    **cb_kwargs
) -> None:
    """
    Тихо отвечает на callback_query, подавляя ошибку
    «query is too old and response timeout expired».
    """
    try:
        await callback.answer(*cb_args, **cb_kwargs)
    except TelegramBadRequest:
        # просто игнорируем устаревший callback
        pass
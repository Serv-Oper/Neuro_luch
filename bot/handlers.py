"""
handlers.py — все хэндлеры Telegram-бота Luch_Neuro
Работает с aiogram 3.x, db.py, ai_service.py, keyboards.py и utils.py
"""

from __future__ import annotations
from db import (
    get_today_total_usage,
    get_user_by_telegram_id,
    bind_telegram,
    unbind_telegram,
    get_user_by_email,
    count_telegram_accounts,
    get_google_account_by_email,
    get_user_message_count,
)
import web.mail_sender as mail_sender
import logging
from aiogram import Bot, Router, F
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ContentType
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardRemove
from aiogram import F as AF  # чтобы не путать наш F
from config import REGISTER_URL
from bot.keyboards import MAIN_MENU_BUTTON
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import date
from config import (
    BOT_TOKEN,
    FREE_DAILY_LIMIT,
    FREE_CHAT_LIMIT,
    PREMIUM_CHAT_LIMIT,
    GUEST_TOTAL_LIMIT,
    SUPPORT_USERNAME,
)
from bot.keyboards import (
    main_menu_keyboard,
    new_chat_keyboard,
    end_chat_keyboard,
    my_chats_keyboard,
    delete_menu_keyboard,
    change_model_keyboard,
    profile_keyboard,
    profile_guest_keyboard,
    auth_choice_keyboard,
    subscription_keyboard,
    about_bot_keyboard,
    faq_keyboard,
    conversation_reply_keyboard,
)
from db import (
    get_or_create_user,
    create_chat,
    finish_chat,
    delete_chat,
    get_or_create_guest_session,
    set_active_chat,
    update_chat_model,
    increment_guest_request,
    get_active_chat,
    get_user_chats,
    SubscriptionStatus,
)
import db
from bot.ai_service import AIService
from bot.utils import (
    handle_errors,
    check_and_increment_usage,
    build_telegram_file_url,
    MissingChatError,
    safe_answer,
    send_final_answer,
    strip_markdown_heads,
    format_html,
    chunk_text,
)
import re
import html
from web.auth import authenticate_user

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML"),
)

# ───────────────────────────────────────────────────────────
#  Хелпер для создания/получения пользователя из Telegram-Update
# ───────────────────────────────────────────────────────────
async def ensure_user(from_user) -> db.User:
    """
    Берёт aiogram.types.User, создаёт запись в БД (если нужно)
    и возвращает ORM-объект User.
    """
    return await get_or_create_user(
        telegram_id=from_user.id,
        username=from_user.username,
    )

router = Router()
service = AIService()

# ───────────  Limits ───────────
MAX_USER_MESSAGES = 200  # maximum messages a single user can send in one chat

def serialize_chats(chats):
    return [
        {"id": c.id, "title": c.title, "created_at": c.created_at, "model_key": c.model_key}
        for c in chats
    ]

# ───────────────────────────────────────────
#  Вспомогательный хелпер: получить User по email
# ───────────────────────────────────────────
async def _get_user_or_notify(email: str, message: Message):
    """
    Пытается найти пользователя по email.
    Если не найден — показывает сообщение и возвращает None,
    чтобы вызывающий код мог прекратить выполнение без дублирования.
    """
    user = await get_user_by_email(email=email)
    if not user:
        await message.answer(
            "❌ Пользователь не найден.",
            reply_markup=main_menu_keyboard()
        )
        return None
    return user

async def _finalize_login(user: db.User, message: Message, state: FSMContext) -> bool:
    """
    Единственное место, где:
      • проверяем лимит Telegram-аккаунтов;
      • привязываем текущий telegram_id;
      • выводим список чатов и сообщение «✅ Вы успешно вошли!».
    Возвращает True, если всё прошло успешно, иначе False.
    """
    user_id = int(user.id)

    # лимит – не больше 2 разных Telegram-аккаунтов
    existing = await count_telegram_accounts(user_id)
    already  = await count_telegram_accounts(user_id,
                                             telegram_id=message.from_user.id)
    if existing >= 2 and already == 0:
        await message.answer(
            "⚠️ Нельзя привязать больше двух Telegram-аккаунтов.",
            reply_markup=main_menu_keyboard()
        )
        await state.clear()
        return False

    # отвязываем старую запись (если была) и привязываем новую
    await unbind_telegram(message.from_user.id)
    await bind_telegram(
        user_id=user_id,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )

    # список чатов
    chats = await get_user_chats(user_id)
    chats_data = [
        {"id": c.id,
         "title": c.title,
         "created_at": c.created_at,
         "model_key": c.model_key}
        for c in chats
    ]
    await message.answer("✅ Вы успешно вошли!",
                         reply_markup=my_chats_keyboard(chats_data))
    await state.clear()
    return True

# ───────────────────────────────────────────
#  FSM — ожидание названия чата
# ───────────────────────────────────────────
class ChatStates(StatesGroup):
    waiting_for_title = State()

class AuthStates(StatesGroup):
    waiting_for_email = State()
    waiting_for_password = State()
    waiting_for_google_code = State()

# ───────────────────────────────────────────
#  /start
# ───────────────────────────────────────────
@router.message(Command("start"))
@handle_errors
async def cmd_start(message: Message):
    # инициализируем гостевую сессию без создания записи в users
    await get_or_create_guest_session(message.from_user.id)

    display = message.from_user.first_name or "друг"
    text = (
        f"Привет, {display}! 👋\n\n"
        "Я — Luch GPT, ваш персональный ассистент.\n"
        "Нажмите кнопку ниже, чтобы начать новый разговор."
    )
    await message.answer(text, reply_markup=main_menu_keyboard())

@router.callback_query(F.data == "show_login")
@handle_errors
async def cb_login(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer(
        "🔐 Введите ваш email для входа:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AuthStates.waiting_for_email)


@router.callback_query(F.data == "show_register")
@handle_errors
async def cb_register(call: CallbackQuery):
    # Убираем «крутилку» Telegram
    await call.answer()

    # Строим inline-клавиатуру с кнопкой регистрации
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Зарегистрироваться", url=REGISTER_URL)
    builder.add(MAIN_MENU_BUTTON)
    builder.adjust(1)

    # Отправляем новое сообщение с кнопкой
    await call.message.answer(
        "📝 Чтобы создать аккаунт, нажмите кнопку ниже:",
        reply_markup=builder.as_markup()
    )

@router.message(AuthStates.waiting_for_email, F.text)
@handle_errors
async def process_login_email(message: Message, state: FSMContext):
    email = message.text.strip()
    await state.update_data(login_email=email)
    # Проверяем, есть ли Google-аккаунт по email
    google_account = await get_google_account_by_email(email)
    if google_account:
        # Отправляем код подтверждения на почту
        await mail_sender.send_confirmation_code(email)
        await state.set_state(AuthStates.waiting_for_google_code)
        await message.answer(
            "📧 На вашу почту отправлен код подтверждения. Введите полученный код:",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        # Переходим к паролю (старая логика)
        await state.set_state(AuthStates.waiting_for_password)
        await message.answer(
            "🔑 Теперь введите пароль:",
            reply_markup=ReplyKeyboardRemove()
        )


# Новый обработчик для AuthStates.waiting_for_google_code
@router.message(AuthStates.waiting_for_google_code, F.text)
@handle_errors
async def process_login_google_code(message: Message, state: FSMContext):
    data = await state.get_data()
    email = data.get("login_email")
    code = message.text.strip()
    # Проверяем код подтверждения
    ok = await mail_sender.verify_code(email, code)
    if not ok:
        await message.answer(
            "❌ Неверный код подтверждения. Попробуйте ещё раз:"
        )
        return
    # Получаем пользователя из БД по email
    user = await get_user_by_email(email=email)
    if not user:
        await message.answer(
            "❌ Пользователь не найден.",
            reply_markup=main_menu_keyboard()
        )
        await state.clear()
        return
    # Финализация входа: лимиты, привязка, вывод чатов
    await _finalize_login(user, message, state)
    return

@router.message(AuthStates.waiting_for_password, F.text)
@handle_errors
async def process_login_password(message: Message, state: FSMContext):
    data = await state.get_data()
    email = data.get("login_email")
    password = message.text.strip()

    # 1) Проверяем учётные данные
    ok = await authenticate_user(email, password)
    if not ok:
        await message.answer(
            "❌ Неверный email или пароль, или почта не подтверждена.",
            reply_markup=main_menu_keyboard()
        )
        await state.clear()
        return

    # 2) Получаем пользователя из БД (через хелпер, без дублирования)
    user = await _get_user_or_notify(email, message)
    if not user:
        await state.clear()
        return

    # Общая финализация входа: лимиты, привязка, вывод чатов
    await _finalize_login(user, message, state)
    return


# ───────────────────────────────────────────
#  Новый разговор
# ───────────────────────────────────────────
@router.callback_query(F.data == "new_chat")
@handle_errors
async def cb_new_chat(call: CallbackQuery):
    # 1) Получаем или создаём пользователя через единый helper
    user = await ensure_user(call.from_user)

    # ── 2) Проверяем гостевой лимит запросов ─────────────────────────
    if user.email is None:
        gs = await get_or_create_guest_session(call.from_user.id)
        if gs.request_count >= GUEST_TOTAL_LIMIT:
            await call.answer("❗️ Лимит гостевых запросов исчерпан", show_alert=True)
            await call.message.answer(
                f"Вы использовали все {GUEST_TOTAL_LIMIT} гостевых запросов.\n"
                "Чтобы продолжить, войдите или зарегистрируйтесь:",
                reply_markup=profile_guest_keyboard()
            )
            return
    # ─────────────────────────────────────────────────────────────────

    # 3) Определяем лимит по подписке
    existing = await get_user_chats(user.id)
    if user.subscription_status == SubscriptionStatus.FREE:
        limit = FREE_CHAT_LIMIT
    else:
        limit = PREMIUM_CHAT_LIMIT

    # 4) Если достигнут лимит одновременных чатов — предлагаем удалить
    if len(existing) >= limit:
        await call.answer(f"Достигнут лимит диалогов ({limit}).", show_alert=True)
        chats_data = [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at,
                "model_key": c.model_key,
            }
            for c in existing
        ]
        await call.message.answer(
            "Удалите один из существующих диалогов, чтобы создать новый:",
            reply_markup=delete_menu_keyboard(chats_data),
        )
        return

    # 5) Всё в порядке — создаём новый чат
    chat = await create_chat(user.id, user.default_model_key)
    mk: str = chat.model_key

    await call.answer()
    # mk — это ключ модели ("fast", "smart" или "vision")
    labels = {"fast": "Быстрая", "smart": "Умная", "vision": "Анализ фото"}
    label = labels.get(mk, mk)  # на случай, если ключ не в словаре

    await call.message.answer(
        f"🆕 Разговор начат\n🧠 Модель: {label}",
        reply_markup=new_chat_keyboard(mk),
    )
    await call.message.answer(
        "Чтобы закончить разговор используйте кнопку ниже",
        reply_markup=conversation_reply_keyboard(),
    )

# ───────────────────────────────────────────
#  Мои разговоры
# ───────────────────────────────────────────
@router.callback_query(F.data == "my_chats")
@handle_errors
async def cb_my_chats(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer()
        await call.message.answer(
            "❗️ Чтобы просмотреть ваши разговоры, войдите или зарегистрируйтесь.",
            reply_markup=auth_choice_keyboard()
        )
        return
    await call.answer()
    await call.message.answer(
        "💬 Ваши разговоры:",
        reply_markup=my_chats_keyboard(
            serialize_chats(await get_user_chats(user.id))
        )
    )

@router.callback_query(F.data == "show_delete_menu")
@handle_errors
async def cb_show_delete_menu(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer()
        await call.message.answer(
            "❗️ Чтобы удалить разговор, войдите или зарегистрируйтесь.",
            reply_markup=auth_choice_keyboard()
        )
        return
    await call.answer()
    await call.message.edit_text(
        "Выберите разговор для удаления:",
        reply_markup=delete_menu_keyboard(serialize_chats(await get_user_chats(user.id))),
    )

@router.callback_query(F.data.startswith("delete_chat:"))
@handle_errors
async def cb_delete_chat(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer()
        await call.message.answer(
            "❗️ Чтобы удалить разговор, войдите или зарегистрируйтесь.",
            reply_markup=auth_choice_keyboard()
        )
        return
    chat_id = int(call.data.split(":", 1)[1])
    await delete_chat(chat_id)
    await call.answer("Разговор удалён.", show_alert=True)
    await call.message.edit_text(
        "💬 Ваши разговоры:",
        reply_markup=my_chats_keyboard(serialize_chats(await get_user_chats(user.id))),
    )


# ───────────────────────────────────────────
#  back / main_menu
# ───────────────────────────────────────────
@router.callback_query(F.data == "back")
@handle_errors
async def cb_back(call: CallbackQuery):
    await call.answer()
    await call.message.answer("Вы вернулись назад:", reply_markup=main_menu_keyboard())

@router.callback_query(F.data == "main_menu")
@handle_errors
async def cb_main_menu(call: CallbackQuery):
    await call.answer()
    await call.message.answer("Главное меню:", reply_markup=main_menu_keyboard())


# ───────────────────────────────────────────
#  Закончить разговор
# ───────────────────────────────────────────
@router.callback_query(F.data == "end_chat")
@handle_errors
async def cb_end_chat(call: CallbackQuery, state: FSMContext):
    # 1) Получаем пользователя и его активный чат
    user = await ensure_user(call.from_user)
    chat = await get_active_chat(user.id)
    if not chat:
        raise MissingChatError("У вас нет активного разговора.")

    # 2) Если у чата уже есть title — просто закрываем без запроса нового
    if chat.title:
        await finish_chat(chat.id)
        await safe_answer(call, "✅ Разговор завершён.")
        # Снимаем reply-клавиатуру
        await call.message.answer(
            "Разговор завершён.",
            reply_markup=ReplyKeyboardRemove()
        )
        # И возвращаем главное меню в виде inline
        await call.message.answer(
            "Выберите действие:",
            reply_markup=main_menu_keyboard()
        )
        return

    # 3) Иначе — переводим FSM в ожидание ввода названия
    await state.set_state(ChatStates.waiting_for_title)
    await state.update_data(chat_id=chat.id)
    await safe_answer(call)
    await call.message.answer(
        "Хотите придумать название для этого разговора?\n"
        "Отправьте его сообщением (до 28 симв.) или нажмите «Пропустить».",
        reply_markup=end_chat_keyboard(),
    )

# ───────────────────────────────────────────
#  Пропустить название
# ───────────────────────────────────────────
@router.callback_query(F.data == "skip_title", ChatStates.waiting_for_title)
@handle_errors
async def cb_skip_title(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    if chat_id:
        await finish_chat(chat_id)
    await state.clear()

    # Закрываем уведомление и логируем в чат
    await safe_answer(call, "Название пропущено.")

    # Снимаем старую inline-клавиатуру и отправляем сообщение без неё
    await call.message.answer(
        "Название пропущено.",
        reply_markup=ReplyKeyboardRemove()
    )

    # Отправляем заново главное меню как inline-клавиатуру
    await call.message.answer(
        "Выберите действие:",
        reply_markup=main_menu_keyboard()
    )


# ───────────────────────────────────────────
#  Сохранение названия
# ───────────────────────────────────────────
@router.message(ChatStates.waiting_for_title, F.text)
@handle_errors
async def save_chat_title(message: Message, state: FSMContext):
    raw = message.text.strip()
    if len(raw) > 28:
        await message.answer(
            f"❗️ Слишком длинное название — максимум 28 символов, у вас {len(raw)}.",
            reply_markup=end_chat_keyboard()
        )
        return

    title = raw  # уже гарантированно ≤28
    data = await state.get_data()
    chat_id = data.get("chat_id")

    if chat_id:
        await finish_chat(chat_id, title=title)

    await state.clear()

    # Подтверждаем сохранение названия и удаляем старую клавиатуру
    await message.answer(
        "✅ Название сохранено.",
        reply_markup=ReplyKeyboardRemove()
    )

    # Отправляем главное меню заново
    await message.answer(
        "Выберите действие:",
        reply_markup=main_menu_keyboard()
    )


# ───────────────────────────────────────────
#  Выбор разговора
# ───────────────────────────────────────────
@router.callback_query(F.data.startswith("select_chat:"))
@handle_errors
async def cb_select_chat(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer()
        await call.message.answer(
            "❗️ Чтобы выбрать разговор, войдите или зарегистрируйтесь.",
            reply_markup=auth_choice_keyboard()
        )
        return

    await state.clear()   # сбрасываем возможное ожидание title
    chat_id = int(call.data.split(":", 1)[1])

    # Проверка на переполненность чата до активации
    cur_user_msgs = await get_user_message_count(chat_id)
    if cur_user_msgs >= MAX_USER_MESSAGES:
        await call.answer()
        await call.message.answer(
            "⚠️ Чат переполнен. Удалите его и начните новый.",
            reply_markup=delete_menu_keyboard([{"id": chat_id}]),
        )
        return

    # Если лимит не превышен — активируем
    await set_active_chat(user.id, chat_id)
    active = await get_active_chat(user.id)
    model_key = str(active.model_key)

    await call.answer()
    await call.message.answer(
        "✅ Разговор активирован.",
        reply_markup=new_chat_keyboard(model_key)
    )


# ───────────────────────────────────────────
#  Изменить модель
# ───────────────────────────────────────────
@router.callback_query(F.data == "change_model")
@handle_errors
async def cb_change_model(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer()
        await call.message.answer(
            "❗️ Чтобы изменить модель, войдите или зарегистрируйтесь.",
            reply_markup=auth_choice_keyboard()
        )
        return
    active = await get_active_chat(user.id)
    if not active:
        raise MissingChatError("У вас нет активного чата.")
    is_premium = user.subscription_status == "premium"
    mk: str = active.model_key
    await call.answer()
    await call.message.answer(
        "Выберите модель:", reply_markup=change_model_keyboard(is_premium, mk)
    )


@router.callback_query(F.data.startswith("model:"))
@handle_errors
async def cb_set_model(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer()
        await call.message.answer(
            "❗️ Чтобы изменить модель, войдите или зарегистрируйтесь.",
            reply_markup=auth_choice_keyboard()
        )
        return
    _, new_key = call.data.split(":", 1)
    if new_key != "fast" and user.subscription_status == "free":
        await call.answer("Недоступно в бесплатном режиме.", show_alert=True)
        return
    active = await get_active_chat(user.id)
    if not active:
        raise MissingChatError("У вас нет активного чата.")
    await update_chat_model(active.id, new_key)  # type: ignore
    await call.answer("Модель изменена.")
    # Словарь с переводом ключей в русские метки
    labels = {"fast": "Быстрая", "smart": "Умная", "vision": "Анализ фото"}
    label = labels.get(new_key, new_key)
    await call.message.answer(
        f"🧠 Модель изменена на {label}",
        reply_markup=new_chat_keyboard(new_key),
    )


@router.callback_query(F.data == "locked_model")
@handle_errors
async def cb_locked_model(call: CallbackQuery):
    await call.answer("Доступно только в платной версии.", show_alert=True)


# ───────────────────────────────────────────
#  Личный кабинет
# ───────────────────────────────────────────

@router.callback_query(F.data == "profile")
@handle_errors
async def cb_profile(call: CallbackQuery, state: FSMContext):
    # Получаем пользователя по Telegram ID
    user = await get_user_by_telegram_id(call.from_user.id)
    # считаем «гостем» также того, у кого нет email
    if user is None or user.email is None:
        gs = await get_or_create_guest_session(call.from_user.id)
        text = (
            "👤 Профиль: гость\n"
            f"📈 Использовано: {gs.request_count} из {GUEST_TOTAL_LIMIT}"
        )
        markup = profile_guest_keyboard()
        await state.clear()
        await call.answer()
        await call.message.answer(text, reply_markup=markup)
        return
    user_id = int(user.id)
    # 3) Авторизованный пользователь
    profile_line = f"👤 Профиль: {user.email}"
    is_free = user.subscription_status == SubscriptionStatus.FREE
    status = "Бесплатный" if is_free else "Премиум"
    expires = user.subscription_expires_at.strftime("%d.%m.%Y") if user.subscription_expires_at else "—"

    if not is_free:
        # PREMIUM
        from db import get_today_usage
        today = date.today()
        used_fast = await get_today_usage(user_id, today, model_key="fast")
        used_smart = await get_today_usage(user_id, today, model_key="smart")
        used_vision = await get_today_usage(user_id, today, model_key="vision")
        text = (
            f"{profile_line}\n"
            f"💎 Статус: {status}\n"
            f"📅 Подписка до: {expires}\n\n"
            f"📈 Использовано сегодня:\n"
            f"  ⚡️ Быстрая: {used_fast} / 45\n"
            f"  🧠 Умная:   {used_smart} / 15\n"
            f"  👁️ Анализ фото:  {used_vision} / 15"
        )
    else:
        # FREE
        used_total = await get_today_total_usage(user_id, date.today())
        text = (
            f"{profile_line}\n"
            f"💎 Статус: {status}\n"
            f"📅 Подписка до: {expires}\n"
            f"📈 Использовано сегодня: {used_total} из {FREE_DAILY_LIMIT}"
        )

    markup = profile_keyboard()
    await state.clear()
    await call.answer()
    await call.message.answer(text, reply_markup=markup)

@router.callback_query(F.data == "auth_choice")
@handle_errors
async def cb_auth_choice(call: CallbackQuery):
    await call.answer()
    # это отправит новое сообщение в чат
    await call.message.answer(
        "Что именно вы хотите сделать?",
        reply_markup=auth_choice_keyboard()
    )

# ───────────────────────────────────────────
#  Подписка
# ───────────────────────────────────────────
@router.callback_query(F.data == "subscription")
@handle_errors
async def cb_subscription(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer()
        await call.message.answer(
            "❗️ Чтобы просмотреть подписку, войдите или зарегистрируйтесь.",
            reply_markup=auth_choice_keyboard()
        )
        return
    is_premium = user.subscription_status == "premium"
    if is_premium:
        expires = user.subscription_expires_at.strftime('%d.%m.%Y') if user.subscription_expires_at else "—"
        text = f"✅ Подписка активна до: {expires}"
    else:
        used = await get_today_total_usage(int(user.id), date.today())
        remaining = max(0, FREE_DAILY_LIMIT - used)
        text = f"🔓 Бесплатный режим. Осталось: {remaining} из {FREE_DAILY_LIMIT}"
    await call.answer()
    await call.message.answer(text, reply_markup=subscription_keyboard(is_premium))


@router.callback_query(F.data == "buy_subscription")
@handle_errors
async def cb_buy_subscription(call: CallbackQuery):
    url = "https://t.me/your_payment_bot"
    await call.answer()
    # ← здесь edit_text → answer
    await call.message.answer(
        f"💳 Перейдите по ссылке для оплаты: {url}",
        reply_markup=subscription_keyboard(False),
    )


# ───────────────────────────────────────────
#  Раздел «О боте» и меню FAQ
# ───────────────────────────────────────────
@router.callback_query(F.data == "about")
@handle_errors
async def cb_about(call: CallbackQuery):
    await call.answer()
    await call.message.answer("ℹ️ Выберите раздел:", reply_markup=about_bot_keyboard())

@router.callback_query(F.data == "faq")
@handle_errors
async def cb_faq_menu(call: CallbackQuery):
    await call.answer()
    await call.message.answer("❓ Вопросы FAQ:", reply_markup=faq_keyboard())

FAQ_ANSWERS = {
    "1": (
        "Регистрация и вход:\n"
        "1. На сайте в разделе «Профиль» нажмите «Регистрация» или «Войти».\n"
        "2. Укажите вашу почту — мы вышлем код подтверждения.\n"
        "3. Введите код на сайте и создайте пароль.\n"
        "4. В боте нажмите «Войти» и введите ту же почту и пароль.\n"
        "(Сейчас регистрация ещё не доступна — следите за обновлениями!)"
    ),
    "2": (
        "Премиум-возможности:\n"
        "Премиум-аккаунт снимает все лимиты на количество диалогов и запросов "
        "к моделям «Умный» и «Анализ фото». Вы получаете приоритетный доступ "
        "к мощным AI-алгоритмам без ожидания и ограничений."
    ),
    "3": (
        "Выбор модели:\n"
        "• Быстрый — мгновенные ответы и идеи за секунды.\n"
        "• Умный — глубокий анализ, разбор сложных вопросов и экспертные советы.\n"
        "• Анализ фото — распознавание, описание и решение задач по изображениям.\n"
        "Переключайтесь через кнопку «🧠 Изменить модель» в любой момент."
    ),
    "4": (
        "Отправка фото:\n"
        "Обязательно пришлите картинку прямо в чат (не документ или файл). "
        "Бот активирует «Анализ фото», распознает текст, опишет содержимое и решит задачи."
    ),
    "5": (
        "Лимиты Free:\n"
        "• 5 запросов в сутки для «быстрой» модели\n"
        "• 5 одновременных чатов\n"
        "При достижении лимита бот предложит перейти на Премиум."
    ),
    "6": (
        "Поддержка:\n"
        "Если возникли вопросы или проблемы, нажмите «ℹ️ О боте → 🆘 Помощь» "
        "и напишите указанному контакту. Мы ответим в течение рабочего дня."
    ),
}

@router.callback_query(F.data.startswith("faq:"))
@handle_errors
async def cb_faq(call: CallbackQuery):
    _, qid = call.data.split(":", 1)
    await call.answer()
    await call.message.answer(
        f"❓ {FAQ_ANSWERS.get(qid, '—')}", reply_markup=faq_keyboard()
    )

@router.callback_query(F.data == "help")
@handle_errors
async def cb_help(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        f"🆘 Пишите @{SUPPORT_USERNAME} — мы поможем!",
        reply_markup=about_bot_keyboard(),
    )

@router.callback_query(F.data == "about_us")
@handle_errors
async def cb_about_us(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        ("Luch Neuro — ваш персональный AI-ассистент, который всегда рядом, чтобы помочь в любых задачах и диалогах.\n\n"
            "Наш сервис объединяет:\n"
            "• ⚡️ Быстрый — молниеносные ответы и идеи за секунды;\n"
            "• 🧠 Умный — глубокий анализ, разбор сложных вопросов и экспертные советы;\n"
            "• 👁️ Анализ фото — распознавание, описание и решение задач прямо на вашем изображении.\n\n"
            "Что вы получаете?\n"
            "  1. 💬 Интуитивный чат с историей переписки и удобным управлением;\n"
            "  2. 🔄 Лёгкая смена режимов под любые ваши запросы;\n"
            "  3. 📈 Прозрачные лимиты и гибкие планы подписки — всегда ясно, сколько осталось.\n\n"
            "🚀 Присоединяйтесь к Luch Neuro и откройте для себя новый уровень взаимодействия с ИИ!"
        ),
        parse_mode="HTML",
        reply_markup=about_bot_keyboard(),
    )


# ───────────────────────────────────────────
#  Обработчик фото
# ───────────────────────────────────────────
@router.message(F.content_type == ContentType.PHOTO)
@handle_errors
async def handle_photo(message: Message):
    # 1) Убеждаемся, что в БД есть пользователь и берём его внутренний id
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )

    # --- Проверяем лимит сообщений в чате ---
    active_chat = await get_active_chat(user.id)
    if not active_chat:
        await message.answer(
            "Сначала начните новый разговор, нажав «🆕 Новый разговор».",
            reply_markup=main_menu_keyboard(),
        )
        return

    cur_user_msgs = await get_user_message_count(int(active_chat.id))  # type: ignore
    if cur_user_msgs >= MAX_USER_MESSAGES:
        await finish_chat(active_chat.id)
        await message.answer(
            "⚠️ Достигнут лимит сообщений. Пожалуйста, начните новый разговор.",
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer("Главное меню:", reply_markup=main_menu_keyboard())
        return

    # 2) Получаем файл и строим URL
    file = await bot.get_file(message.photo[-1].file_id)
    image_url = build_telegram_file_url(file)

    # 3) Запрашиваем анализ изображения, передавая либо подпись, либо явный промпт
    if message.caption and message.caption.strip():
        prompt = message.caption.strip()
    else:
        prompt = (
            "Пожалуйста, проанализируй это изображение и опиши всё, что на нём видно, "
            "Если на нём что-то видно — например, задачи, тесты или другие задания — также реши их максимально правильно."
        )

    # 3.5) Проверяем и инкрементируем дневной лимит перед анализом фото
    await check_and_increment_usage(
        user_id=user.id,
        model_key=str(active_chat.model_key),
        subscription_status=user.subscription_status,
    )

    answer = await service.analyze_image(
        user_id=user.id,
        image_url=image_url,
        prompt=prompt
    )

    # 5) Логируем ответ
    logger.debug(
        "→ BOT image-analysis reply to user=%s: %r",
        message.from_user.id,
        answer
    )
    # 6) Преобразуем Markdown-подобный ответ в HTML и разбиваем на части
    cleaned = strip_markdown_heads(answer)
    formatted = format_html(cleaned)
    parts = chunk_text(formatted)
    # 7) Шлём каждую часть с HTML-разметкой, прикрепляя клавиатуру только к последней
    for idx, part in enumerate(parts):
        markup = conversation_reply_keyboard() if idx == len(parts) - 1 else None
        await message.answer(
            part,
            parse_mode="HTML",
            reply_markup=markup,
        )

# ───────────────────────────────────────────
#  Обработчик нажатия reply-кнопки "🛑 Закончить разговор"
# ───────────────────────────────────────────

@router.message(AF.text == "🛑 Закончить разговор")
@handle_errors
async def handle_reply_end(message: Message, state: FSMContext):
    # 1) Получаем пользователя и его активный чат
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )
    chat = await get_active_chat(user.id)
    if not chat:
        # если нет активного разговора — выходим
        raise MissingChatError("У вас нет активного разговора.")

    # 2) Сразу убираем закреплённую reply-клавиатуру
    await message.answer(
        "Выход из режима разговора...",
        reply_markup=ReplyKeyboardRemove()
    )

    # 3) Если у чата уже есть title — просто закрываем
    if chat.title:
        await finish_chat(chat.id)
        await message.answer(
            "✅ Разговор завершён.",
            reply_markup=main_menu_keyboard()
        )
        return

    # 4) Иначе — переводим FSM в ожидание ввода названия
    await state.set_state(ChatStates.waiting_for_title)
    await state.update_data(chat_id=chat.id)
    # показываем inline-кнопки «Пропустить / Назад»
    await message.answer(
        "Хотите придумать название для этого разговора?\n"
        "Отправьте его сообщением или нажмите «Пропустить».",
        reply_markup=end_chat_keyboard(),
    )

# ───────────────────────────────────────────
#  Обработчик текстовых сообщений (обычные сообщения)
# ───────────────────────────────────────────
@router.message(F.text)
@handle_errors
async def handle_text(message: Message):
    # 1) Получаем или создаём пользователя
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )

    # 2) Проверяем, есть ли у пользователя активный чат
    active_chat = await get_active_chat(user.id)
    if not active_chat:
        await message.answer(
            "Чтобы задать вопрос нейросети, сначала начните на кнопку «новый разговор»",
            reply_markup=main_menu_keyboard()
        )
        return

    # --- Лимит сообщений от пользователя в одном чате ---
    cur_user_msgs = await get_user_message_count(int(active_chat.id))
    if cur_user_msgs >= MAX_USER_MESSAGES:
        await finish_chat(active_chat.id)
        await message.answer(
            "⚠️ Достигнут лимит сообщений. Пожалуйста, начните новый разговор.",
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer("Главное меню:", reply_markup=main_menu_keyboard())
        return

    # 3) Гостевой лимит (только внутри активного чата)
    if user.email is None:
        gs = await get_or_create_guest_session(message.from_user.id)
        cur = await increment_guest_request(gs.session_token)
        if cur > GUEST_TOTAL_LIMIT:
            await message.answer(
                f"❗️ Лимит гостевых запросов ({GUEST_TOTAL_LIMIT}) исчерпан.\n"
                "Чтобы продолжить, войдите или зарегистрируйтесь:",
                reply_markup=profile_guest_keyboard()
            )
            return

    # 4) Проверяем и инкрементируем дневной лимит перед запросом
    await check_and_increment_usage(
        user_id=user.id,
        model_key=str(active_chat.model_key),
        subscription_status=user.subscription_status,
    )

    # 5) Запрашиваем ответ у AI-сервиса
    answer = await service.chat_complete(user.id, message.text)

    # 6) Логируем и извлекаем «Мысли» для smart-модели
    logger.debug("→ BOT reply to user=%s: %r", message.from_user.id, answer)
    think_text = ""
    body = answer

    if active_chat.model_key == "smart":
        # Попытка найти полный тег <think>…</think> и разделить
        m = re.search(r"(?is)<think>(.*?)</think>(.*)", answer)
        if not m:
            # Если нет открывающего тега, ловим всё до первого </think>
            m = re.search(r"(?is)^(.*?)</think>(.*)", answer)
        if m:
            think_text = m.group(1).strip()
            # Убираем случайный остаток открывающего тега
            think_text = re.sub(r"(?is)^<think>\s*", "", think_text).strip()
            body = m.group(2).strip()

    # 7) Отправляем «Мысли», если есть
    if think_text:
        await message.answer(
            "<b>Мысли:</b>\n"
            f"<blockquote expandable>{html.escape(think_text)}</blockquote>",
            parse_mode="HTML"
        )

    # 8) Отправляем итоговый ответ
    if active_chat.model_key == "smart":
        # — для smart: разбиваем на части и выводим с заголовком
        await send_final_answer(
            message,
            raw_body=body,
            reply_markup=conversation_reply_keyboard()
        )
    else:
        # — для fast/vision: простое разбиение без заголовка
        cleaned = strip_markdown_heads(body)
        formatted = format_html(cleaned)
        parts = chunk_text(formatted)

        kb = conversation_reply_keyboard()
        for idx, part in enumerate(parts):
            markup = kb if idx == len(parts) - 1 else None
            await message.answer(
                part,
                reply_markup=markup,
                parse_mode="HTML"
            )


# ───────────────────────────────────────────
#  Запуск (использовать в main.py)
# ───────────────────────────────────────────
async def start_bot():
    from aiogram import Dispatcher

    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)
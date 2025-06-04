from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ──────────────────────────────────────────────────
# Digit emoji mapping for dynamic numbering
# ──────────────────────────────────────────────────
DIGIT_EMOJI: dict[str, str] = {
    "0": "0️⃣",
    "1": "1️⃣",
    "2": "2️⃣",
    "3": "3️⃣",
    "4": "4️⃣",
    "5": "5️⃣",
    "6": "6️⃣",
    "7": "7️⃣",
    "8": "8️⃣",
    "9": "9️⃣",
}

# ──────────────────────────────────────────────────
# Emojis for model labels
# ──────────────────────────────────────────────────
EMOJI = {
    "fast": "⚡️",
    "smart": "🧠",
    "vision": "👁️",
}

# ──────────────────────────────────────────────────
# Common navigation buttons
# ──────────────────────────────────────────────────
BACK_BUTTON = InlineKeyboardButton(text="🔙 Назад", callback_data="back")
MAIN_MENU_BUTTON = InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")

# ──────────────────────────────────────────────────
# Keyboards for guest authentication flow
# ──────────────────────────────────────────────────
def profile_guest_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопки «Войти / Регистрация» и «Подписка» для гостевого профиля
    """
    b = InlineKeyboardBuilder()
    # Первая строка: вход или регистрация
    b.button(text="📲 Войти / 📋Регистрация", callback_data="auth_choice")
    # Вторая строка: подписка
    b.button(text="💎 Подписка", callback_data="subscription")
    b.adjust(1, 1)  # две кнопки в две строки
    return b.as_markup()


def auth_choice_keyboard() -> InlineKeyboardMarkup:
    """
    Меню выбора: Войти или Регистрация
    """
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📲 Войти", callback_data="show_login"),
        InlineKeyboardButton(text="📋 Регистрация", callback_data="show_register"),
    )
    b.adjust(1)
    return b.as_markup()

# ──────────────────────────────────────────────────
# Conversation state reply keyboard
# ──────────────────────────────────────────────────
def conversation_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    ReplyKeyboardMarkup с кнопкой 🛑 Закончить разговор
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛑 Закончить разговор")] ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

# ──────────────────────────────────────────────────
# Main menu keyboard
# ──────────────────────────────────────────────────
def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Главное меню (inline):
    🆕 Новый разговор
    💬 Мои разговоры
    👤 Личный кабинет
    💎 Подписка
    ℹ️ О боте
    """
    b = InlineKeyboardBuilder()
    b.button(text="🆕 Новый разговор", callback_data="new_chat")
    b.button(text="💬 Мои разговоры", callback_data="my_chats")
    b.button(text="👤 Личный кабинет", callback_data="profile")
    b.button(text="💎 Подписка", callback_data="subscription")
    b.button(text="ℹ️ О боте", callback_data="about")
    b.adjust(1)
    return b.as_markup()

# ──────────────────────────────────────────────────
# New chat options keyboard
# ──────────────────────────────────────────────────
def new_chat_keyboard(default_model: str = "fast") -> InlineKeyboardMarkup:
    """
    Меню после создания нового разговора: 🧠 Изменить модель + 🏠 Меню
    """
    icon = EMOJI.get(default_model, "")
    b = InlineKeyboardBuilder()
    b.button(text=f"🧠 Изменить модель ({icon})", callback_data="change_model")
    b.add(MAIN_MENU_BUTTON)
    b.adjust(1)
    return b.as_markup()

# ──────────────────────────────────────────────────
# End chat naming keyboard
# ──────────────────────────────────────────────────
def end_chat_keyboard() -> InlineKeyboardMarkup:
    """
    После нажатия "Закончить разговор": 🚫 Пропустить + 🔙 Назад
    """
    b = InlineKeyboardBuilder()
    b.button(text="🚫 Пропустить", callback_data="skip_title")
    b.add(BACK_BUTTON)
    b.adjust(1)
    return b.as_markup()

# ──────────────────────────────────────────────────
# Change model selection keyboard
# ──────────────────────────────────────────────────
def change_model_keyboard(is_premium: bool, current_model: str) -> InlineKeyboardMarkup:
    """
    Выбор модели в активном чате
    """
    b = InlineKeyboardBuilder()
    # Русские названия: "fast" → "Быстрая", "smart" → "Умная", "vision" → "Анализ фото"
    labels = {"fast": "Быстрая", "smart": "Умная", "vision": "Анализ фото"}
    for key, icon in EMOJI.items():
        if key == current_model:
            prefix = "✅"
        elif not is_premium and key != "fast":
            prefix = "❌"
        else:
            prefix = "🔘"
        text = f"{prefix} {labels.get(key, key)} {icon}"
        cb = "locked_model" if prefix == "❌" else f"model:{key}"
        b.button(text=text, callback_data=cb)
    b.add(BACK_BUTTON)
    b.adjust(1)
    return b.as_markup()

# ──────────────────────────────────────────────────
# My chats keyboard with dynamic numbering
# ──────────────────────────────────────────────────
def my_chats_keyboard(chats: list[dict]) -> InlineKeyboardMarkup:
    """
    Меню «Мои разговоры» с нумерацией эмодзи
    """
    b = InlineKeyboardBuilder()
    for idx, chat in enumerate(chats, start=1):
        created = chat["created_at"].strftime("%d.%m")
        title = chat.get("title") or created
        emoji = EMOJI.get(chat.get("model_key", "fast"), EMOJI["fast"])
        number_emoji = "".join(DIGIT_EMOJI[d] for d in str(idx))
        b.button(
            text=f"{number_emoji} {title} | {emoji}",
            callback_data=f"select_chat:{chat['id']}"
        )
    b.adjust(1)
    b.row(
        InlineKeyboardButton(text="🗑️ Удалить разговор", callback_data="show_delete_menu"),
        BACK_BUTTON
    )
    return b.as_markup()

# ──────────────────────────────────────────────────
# Delete chat menu keyboard
# ──────────────────────────────────────────────────
def delete_menu_keyboard(chats: list[dict]) -> InlineKeyboardMarkup:
    """
    Меню удаления разговоров + Назад
    """
    b = InlineKeyboardBuilder()
    for chat in chats:
        created = chat["created_at"].strftime("%d.%m")
        title = chat.get("title") or created
        emoji = EMOJI.get(chat.get("model_key", "fast"), EMOJI["fast"])
        b.button(
            text=f"🗑️ {title} | {emoji}",
            callback_data=f"delete_chat:{chat['id']}"
        )
    b.adjust(1)
    b.row(BACK_BUTTON)
    return b.as_markup()

# ──────────────────────────────────────────────────
# Profile keyboard for authenticated users
# ──────────────────────────────────────────────────
def profile_keyboard() -> InlineKeyboardMarkup:
    """
    Личный кабинет (inline): 💎 Подписка + 🔙 Назад
    """
    b = InlineKeyboardBuilder()
    b.button(text="💎 Подписка", callback_data="subscription")
    b.add(BACK_BUTTON)
    b.adjust(1)
    return b.as_markup()

# ──────────────────────────────────────────────────
# Subscription keyboard
# ──────────────────────────────────────────────────
def subscription_keyboard(is_premium: bool) -> InlineKeyboardMarkup:
    """
    Меню подписки: оформление + Назад
    """
    b = InlineKeyboardBuilder()
    if not is_premium:
        b.button(text="💳 Оформить подписку", callback_data="buy_subscription")
    b.add(BACK_BUTTON)
    b.adjust(1)
    return b.as_markup()

# ──────────────────────────────────────────────────
# About bot keyboard
# ──────────────────────────────────────────────────
def about_bot_keyboard() -> InlineKeyboardMarkup:
    """
    Подменю "О боте": FAQ, Помощь, О нас, Назад
    """
    b = InlineKeyboardBuilder()
    b.button(text="❓ FAQ", callback_data="faq")
    b.button(text="🆘 Помощь", callback_data="help")
    b.button(text="📢 О нас", callback_data="about_us")
    b.add(BACK_BUTTON)
    b.adjust(1)
    return b.as_markup()

# ──────────────────────────────────────────────────
# FAQ keyboard
# ──────────────────────────────────────────────────
def faq_keyboard() -> InlineKeyboardMarkup:
    """
    Подменю FAQ — список вопросов + Назад
    """
    b = InlineKeyboardBuilder()
    b.button(text="Регистрация и вход", callback_data="faq:1")
    b.button(text="Премиум-возможности", callback_data="faq:2")
    b.button(text="Выбор модели", callback_data="faq:3")
    b.button(text="Отправка фото", callback_data="faq:4")
    b.button(text="Лимиты Free", callback_data="faq:5")
    b.button(text="Поддержка", callback_data="faq:6")
    b.add(BACK_BUTTON)
    b.adjust(1)
    return b.as_markup()
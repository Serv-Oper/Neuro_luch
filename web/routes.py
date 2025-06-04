async def _apply_usage_limit(user):
    """
    Helper to apply daily usage limit for a user in API routes.
    """
    chat = await get_active_chat(user.id)
    mk: str = cast(str, chat.model_key)
    sub_status: SubscriptionStatus = cast(SubscriptionStatus, user.subscription_status)
    try:
        await check_and_increment_usage(
            user_id=user.id,
            model_key=mk,
            subscription_status=sub_status,
        )
    except LimitExceededError as le:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(le))
# web/routes.py
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, constr
from db import get_user_by_email
from db import update_chat_title
from web.auth import (
    register_user,
    confirm_user_email,
    authenticate_user,
    authenticate_google,
    create_guest_token,
    verify_guest_token,
    create_access_token,
    decode_token,
)
from bot.ai_service import AIService
from bot.utils import check_and_increment_usage, LimitExceededError
from db import get_user_message_count
from db import (
    get_or_create_user,
    get_user_chats,
    create_chat,
    set_active_chat,
    get_active_chat,
    delete_chat,
    finish_chat,
    get_today_total_usage,
    get_last_limited_messages,
    reset_today_usage,
)
from db import SubscriptionStatus
from db import get_guest_session
from config import GUEST_TOTAL_LIMIT, FREE_DAILY_LIMIT

from typing import cast
from typing import List
from fastapi import Query
from datetime import datetime
from db import get_today_usage


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login/email")
router = APIRouter(prefix="/api", tags=["api"])
ai_service = AIService()


# ─────────── Schemas ───────────
class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class ConfirmIn(BaseModel):
    email: EmailStr
    code: str


class LoginEmailIn(BaseModel):
    email: EmailStr
    password: str


class LoginGoogleIn(BaseModel):
    id_token: str


class ChatMsgIn(BaseModel):
    chat_id: int | None = None
    message: str


class ChangeModelIn(BaseModel):
    chat_id: int
    model_key: str

    model_config = {
        "protected_namespaces": (),
    }

class ChatSelectIn(BaseModel):
    chat_id: int

class ChatDeleteIn(BaseModel):
    chat_id: int

class ChatEndIn(BaseModel):
    chat_id: int

class ChatTitleIn(BaseModel):
    chat_id: int
    # автоматически приведёт к str и обрежет лишние пробелы
    title: constr(strip_whitespace=True, min_length=1, max_length=28)

class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime
    prompt_tokens: int | None
    completion_tokens: int | None


# ─────────── Dependencies ───────────
async def get_current_subject(token: str = Depends(oauth2_scheme)) -> str:
    """
    Декодируем JWT, возвращаем sub (email или guest-token).
    Если это гостевой токен — проверяем лимит.
    """
    sub = await decode_token(token)
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    # если это не email — считаем гостевым
    if "@" not in sub:
        if not await verify_guest_token(sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guest limit exceeded"
            )
    return sub


async def require_email_user(sub: str = Depends(get_current_subject)) -> str:
    """
    Убеждаемся, что sub — это email. Иначе 403.
    """
    if "@" not in sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only registered users can use this endpoint"
        )
    return sub


# ─────────── Endpoints ───────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def api_register(body: RegisterIn):
    await register_user(str(body.email), body.password)
    return {"detail": "ok"}


@router.post("/confirm")
async def api_confirm(body: ConfirmIn):
    ok = await confirm_user_email(str(body.email), body.code)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code or expired")
    return {"detail": "email confirmed"}


@router.post("/login/email")
async def api_login_email(form: OAuth2PasswordRequestForm = Depends()):
    if not await authenticate_user(form.username, form.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad credentials or not confirmed"
        )
    token = create_access_token(sub=form.username)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login/google")
async def api_login_google(body: LoginGoogleIn):
    email = await authenticate_google(body.id_token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid Google token")
    token = create_access_token(sub=email)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login/guest")
async def api_login_guest():
    token = await create_guest_token()
    return {"access_token": token, "token_type": "bearer"}


@router.get("/chats")
async def list_chats(user_email: str = Depends(require_email_user)):
    user = await get_or_create_user(email=user_email)
    chats = await get_user_chats(user.id)
    return chats


@router.post("/chat/message")
async def chat_text(
    data: ChatMsgIn,
    subject: str = Depends(get_current_subject),
):
    # Получаем пользователя (может быть как зарегистрированный, так и гостевой)
    user = await get_or_create_user(email=subject)

    # 1) создать или активировать чат
    if data.chat_id is None:
        chat = await create_chat(user.id, user.default_model_key)
        chat_id = chat.id
    else:
        chat_id = data.chat_id
        await set_active_chat(user.id, chat_id)

    # === НОВАЯ ПРОВЕРКА ЛИМИТА: максимум 200 сообщений от USER в одном чате ===
    max_user_messages = 200
    cur_count = await get_user_message_count(chat_id)
    if cur_count >= max_user_messages:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Лимит в {max_user_messages} сообщений от вас в одном чате достигнут. Пожалуйста, создайте новый чат."
        )

    # 2) отправить в AI
    answer = await ai_service.chat_complete(user.id, data.message)

    # Проверка дневного лимита
    await _apply_usage_limit(user)

    return {"chat_id": chat_id, "answer": answer}


@router.post("/chat/image")
async def chat_image(
    # chat_id можно передавать как строку: "null" или отсутствует — будет создан новый диалог
    chat_id: str | None = Query(None),
    file: UploadFile = File(...),
    prompt: str | None = Form(None),
    subject: str = Depends(get_current_subject),
):
    # 1) Доступ только для email-пользователей
    if "@" not in subject:
        raise HTTPException(status_code=403, detail="Only registered users can analyze images")

    # 2) Получаем пользователя
    user = await get_or_create_user(email=subject)

    # 2.1) Преобразуем параметр chat_id: "null" или "" считаются отсутствием
    if chat_id in (None, "", "null"):
        real_chat_id: int | None = None
    else:
        try:
            real_chat_id = int(chat_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="chat_id должен быть целым числом или null")

    # 2.2) Если chat_id отсутствует, создаем новый чат с моделью vision
    if real_chat_id is None:
        chat = await create_chat(user.id, model_key="vision")      # vision – спец-модель для картинок
        real_chat_id = chat.id
    else:
        # Если чат уже существует — принудительно переключаем его модель на vision
        await set_active_chat(user.id, real_chat_id, model_key="vision")

    # 3) Контроль размера (< 20 MB) и MIME-типа
    if file.content_type.split("/")[0] != "image":
        raise HTTPException(status_code=415, detail="Only image files are allowed")
    max_size = 20 * 1024 * 1024  # 20 MB
    image_bytes = await file.read()
    if len(image_bytes) > max_size:
        raise HTTPException(status_code=413, detail="Image is too large (limit 20 MB)")

    # 4) Промпт по умолчанию
    used_prompt = prompt.strip() if prompt and prompt.strip() else (
        "Пожалуйста, проанализируй это изображение и опиши всё, что на нём видно. Отвечай на русском, если тебя не просят ответить на другом языке."
        "Если на нём есть задачи или тесты — также реши их максимально правильно."
    )

    # 5) Анализ изображения (теперь модель гарантированно vision)
    try:
        answer = await ai_service.analyze_image_bytes(user.id, image_bytes, used_prompt)
    except RuntimeError as e:
        # Здесь ловим случаи, когда внешний API три раза вернул 429/другую ошибку.
        # Отдаём пользователю явный HTTP 503 (Service Unavailable) с текстом из e.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Не удалось получить ответ от vision-модели: {e}"
        )

    # 6) Лимит запросов
    await _apply_usage_limit(user)

    # 7) Возвращаем и ответ, и id созданного/использованного чата
    return {"chat_id": real_chat_id, "answer": answer}

@router.get("/chat/active")
async def api_active_chat(subject: str = Depends(get_current_subject)):
    if "@" not in subject:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only registered users can select chats")
    user = await get_or_create_user(email=subject)
    chat = await get_active_chat(user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active chat")
    return chat

@router.post("/chat/select")
async def api_select_chat(data: ChatSelectIn, subject: str = Depends(get_current_subject)):
    if "@" not in subject:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only registered users can select chats")
    user = await get_or_create_user(email=subject)
    await set_active_chat(user.id, data.chat_id)
    chat = await get_active_chat(user.id)
    return chat

@router.post("/chat/delete")
async def api_delete_chat(data: ChatDeleteIn, subject: str = Depends(get_current_subject)):
    if "@" not in subject:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only registered users can delete chats")
    await delete_chat(data.chat_id)
    return {"detail": "chat deleted"}

@router.post("/chat/end")
async def api_end_chat(data: ChatEndIn, subject: str = Depends(get_current_subject)):
    if "@" not in subject:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only registered users can end chats")
    await finish_chat(data.chat_id)
    return {"detail": "chat ended"}


@router.post("/chat/title", status_code=status.HTTP_200_OK)
async def api_title_chat(
    data: ChatTitleIn,
    email: str = Depends(get_current_subject),
):
    # 1) Проверяем, что это пользователь
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(403, "Только зарегистрированные могут менять название")

    # 2) Проверяем, что чат у него есть
    chats = await get_user_chats(int(user.id))
    if data.chat_id not in {c.id for c in chats}:
        raise HTTPException(404, "Чат не найден или нет прав")

    # 3) Сохраняем title
    await update_chat_title(data.chat_id, data.title)

    return {"detail": "Название успешно сохранено"}

@router.get("/profile")
async def api_profile(subject: str = Depends(require_email_user)):
    user = await get_or_create_user(email=subject)
    # 1) Если это гостевой аккаунт
    if user.email is None:
        gs = await get_guest_session(session_token=subject)
        return {
            "profile": "guest",
            "used": gs.request_count,
            "limit": GUEST_TOTAL_LIMIT
        }

    # 2) Зарегистрированный пользователь
    from datetime import date
    today = date.today()

    # 2.1) Для Free-подписки — возвращаем общий использованный счётчик
    if user.subscription_status == SubscriptionStatus.FREE:
        used_total = await get_today_total_usage(int(user.id), today)
        return {
            "email": user.email,
            "status": "Бесплатный",
            "expires": user.subscription_expires_at,
            "used_today": used_total,
            "limit": FREE_DAILY_LIMIT
        }

    # 2.2) Для Премиум-подписки — возвращаем разбивку по моделям
    used_fast  = await get_today_usage(int(user.id), today, model_key="fast")
    used_smart = await get_today_usage(int(user.id), today, model_key="smart")
    used_vision= await get_today_usage(int(user.id), today, model_key="vision")

    return {
        "email": user.email,
        "status": "Премиум",
        "expires": user.subscription_expires_at,
        "usage": {
            "fast":  { "used": used_fast,   "limit": 45 },
            "smart": { "used": used_smart,  "limit": 15 },
            "vision":{ "used": used_vision, "limit": 15 }
        }
    }

@router.post("/chat/model")
async def change_chat_model(
    data: ChangeModelIn,
    subject: str = Depends(get_current_subject),
):
    if "@" not in subject:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only registered users can change chat model"
        )
    user = await get_or_create_user(email=subject)

    # **здесь проверяем подписку**
    if data.model_key != "fast" and user.subscription_status == SubscriptionStatus.FREE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Model change is not available in free plan"
        )

    # теперь меняем
    await set_active_chat(user.id, data.chat_id, model_key=data.model_key)
    return {
        "detail": "model changed",
        "chat_id": data.chat_id,
        "model_key": data.model_key
    }


# Получить сообщения чата по chat_id (от старых к новым)
# Получить сообщения чата по chat_id (от старых к новым, но итоговая отдача уже «перевернутая»)
@router.get(
    "/chat/talk/{chat_id}",
    response_model=List[MessageOut],
    summary="Получить сообщения чата (максимум по лимитам USER/BOT)",
)
async def api_get_chat_messages(
    chat_id: int,
    max_user: int = Query(120, ge=0, le=120),
    max_bot: int = Query(120, ge=0, le=120),
    subject: str = Depends(get_current_subject),
):
    # 1) Доступ только для зарегистрированных пользователей
    if "@" not in subject:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only registered users can view chat messages",
        )

    # 2) Проверяем, что пользователь владеет этим chat_id
    user = await get_or_create_user(email=subject)
    user_chats = await get_user_chats(user.id)
    if chat_id not in {c.id for c in user_chats}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found or no permission",
        )

    # 3) Получаем из БД список сообщений от старых к новым
    messages = await get_last_limited_messages(
        chat_id,
        max_user=max_user,
        max_bot=max_bot
    )

    # 4) Переворачиваем список, чтобы фронтендер не делал .reverse()
    return [
        {
            "id": m.id,
            "role": m.role.value,
            "content": m.content,
            "timestamp": m.timestamp,
            "prompt_tokens": m.prompt_tokens,
            "completion_tokens": m.completion_tokens,
        }
        for m in reversed(messages)
    ]

@router.post("/test/reset-usage")
async def api_reset_usage(email: str = Depends(require_email_user)):
    user = await get_or_create_user(email=email)
    await reset_today_usage(user.id)
    return {"detail": "usage reset"}
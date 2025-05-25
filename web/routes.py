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
from db import (
    get_or_create_user,
    get_user_chats,
    create_chat,
    set_active_chat,
    get_active_chat,
    delete_chat,
    finish_chat,
    get_today_total_usage,
)
from db import SubscriptionStatus
from db import get_guest_session
from config import GUEST_TOTAL_LIMIT, FREE_DAILY_LIMIT

from typing import cast

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
    # только авторизованные email-пользователи могут работать с чатами
    if "@" not in subject:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only registered users can chat"
        )
    user = await get_or_create_user(email=subject)

    # 1) создать или активировать чат
    if data.chat_id is None:
        chat = await create_chat(user.id, user.default_model_key)
        chat_id = chat.id
    else:
        chat_id = data.chat_id
        await set_active_chat(user.id, chat_id)

    # 2) отправить в AI
    answer = await ai_service.chat_complete(user.id, data.message)

    # Проверка дневного лимита
    await _apply_usage_limit(user)

    return {"chat_id": chat_id, "answer": answer}


@router.post("/chat/image")
async def chat_image(
    chat_id: int,
    file: UploadFile = File(...),
    prompt: str | None = Form(None),
    subject: str = Depends(get_current_subject),
):
    # 1) Доступ только для email-пользователей
    if "@" not in subject:
        raise HTTPException(status_code=403, detail="Only registered users can analyze images")

    # 2) Пользователь и активный чат
    user = await get_or_create_user(email=subject)
    await set_active_chat(user.id, chat_id)

    # 3) Контроль размера (< 5 MB) и MIME-типа
    if file.content_type.split("/")[0] != "image":
        raise HTTPException(status_code=415, detail="Only image files are allowed")
    max_size = 5 * 1024 * 1024  # 5 MB
    image_bytes = await file.read()
    if len(image_bytes) > max_size:
        raise HTTPException(status_code=413, detail="Image is too large (limit 5 MB)")

    # 4) Промпт по умолчанию
    used_prompt = prompt.strip() if prompt and prompt.strip() else (
        "Пожалуйста, проанализируй это изображение и опиши всё, что на нём видно. "
        "Если на нём есть задачи или тесты — также реши их максимально правильно."
    )

    # 5) Анализ изображения без сохранения файла
    answer = await ai_service.analyze_image_bytes(user.id, image_bytes, used_prompt)

    # 6) Лимит запросов
    await _apply_usage_limit(user)

    return {"answer": answer}

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
    # guest
    if user.email is None:
        gs = await get_guest_session(session_token=subject)  # or by telegram ID?
        return {"profile": "guest", "used": gs.request_count, "limit": GUEST_TOTAL_LIMIT}
    # registered
    from datetime import date
    used_total = await get_today_total_usage(int(user.id), date.today())
    return {
        "email": user.email,
        "status": user.subscription_status,
        "expires": user.subscription_expires_at,
        "used_today": used_total,
        "limit": FREE_DAILY_LIMIT if user.subscription_status == SubscriptionStatus.FREE else None,
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
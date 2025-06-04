import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional
import ssl
import certifi
from aiohttp import ClientTimeout
from bot.utils import MissingChatError
from config import IO_API_KEY
from db import (
    MessageRole,
    get_active_chat,
    get_chat_messages,
    add_message,
    get_model_by_key,
)

logger = logging.getLogger(__name__)

class AIService:
    BASE_URL = "https://api.intelligence.io.solutions/api/v1"
    MAX_RETRIES = 3
    RETRY_BACKOFF = 1  # seconds multiplier
    DEFAULT_TIMEOUT = 60  # seconds

    def __init__(self, api_key: str = IO_API_KEY):
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            # создаём SSL-контекст с корнями из certifi
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)

            # передаём тот же заголовок и наш connector
            self._session = aiohttp.ClientSession(
                headers=self._headers,
                connector=connector,
            )
        return self._session

    async def _request(self, method: str, path: str, **kwargs) -> Dict:
        """
        Унифицированный запрос с retry/backoff.
        """
        # Apply default timeout if none provided
        if "timeout" not in kwargs or kwargs.get("timeout") is None:
            kwargs["timeout"] = ClientTimeout(total=self.DEFAULT_TIMEOUT)

        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                async with session.request(method, url, **kwargs) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status in (429, 500, 502, 503, 504):
                        retry_after = resp.headers.get("Retry-After")
                        delay = int(retry_after) if retry_after and retry_after.isdigit() else self.RETRY_BACKOFF * (2 ** (attempt - 1))
                        logger.warning(f"[{resp.status}] {method} {url}, retry {attempt} after {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        error_body = await resp.text()
                        logger.error(f"HTTP {resp.status} error body: {error_body}")
                        resp.raise_for_status()
            except Exception as e:
                logger.error(f"Error on {method} {url}: {e}")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_BACKOFF * (2 ** (attempt - 1)))
                    continue
                raise

        raise RuntimeError(f"Failed {method} {url} after {self.MAX_RETRIES} attempts")

    async def get_available_models(self) -> Dict[str, str]:
        """
        Получить список chat-моделей и embedding-моделей, обновить таблицу models.
        Возвращает dict key_name -> model_id.
        """
        data = await self._request("GET", "/models")
        chat_models = {m["id"].split("/")[-1]: m["id"] for m in data.get("data", [])}

        data = await self._request("GET", "/embedding-models")
        embed_models = {m["id"].split("/")[-1]: m["id"] for m in data.get("data", [])}

        return {**chat_models, **embed_models}

    async def chat_complete(self, user_id: int, prompt: str) -> str:
        """
        Основной метод общения: берёт активный Chat по внутреннему user_id,
        загружает историю, отправляет запрос, сохраняет сообщения (с учётом токенов)
        и возвращает ответ.
        """
        # 1) Находим активный чат по внутреннему ID пользователя
        chat = await get_active_chat(user_id)
        if chat is None:
            raise MissingChatError(
                "Нет активного разговора\n"
                "Чтобы получить ответ от нейросети, нажмите «🆕 Новый разговор»"
            )

        # 2) Получаем модель из БД
        model = await get_model_by_key(chat.model_key)
        if not model:
            raise RuntimeError(f"Модель '{chat.model_key}' не найдена или неактивна.")

        # 3) Собираем историю сообщений
        history = await get_chat_messages(chat.id)

        # 4) Вставляем нашу system‐роль для smart-модели, если нужно
        if chat.model_key == "smart":
            system_content = (
                "You are Luch Neuro (also known as Luch GPT), an expert AI assistant "
                "who deeply understands any topic the user brings up. Always introduce "
                "yourself as “Luch Neuro” or “Luch GPT” if asked. Your default reply "
                "language is Russian—use Russian in your answers unless the user writes "
                "in another language or explicitly requests a different language. Be thorough, "
                "accurate, and professional, while keeping your tone friendly and helpful."
            )
        else:
            system_content = ""

        messages: list[dict] = [{"role": "system", "content": system_content}]
        for msg in history:
            messages.append({"role": msg.role.value, "content": msg.content})
        messages.append({"role": "user", "content": prompt})

        # 5) Делаем запрос к API
        payload = {"model": model.model_id, "messages": messages}
        data = await self._request(
            "POST",
            "/chat/completions",
            json=payload,
            timeout=60
        )

        # 6) Извлекаем ответ и статистику токенов
        choice = data["choices"][0]["message"]
        response_text: str = choice["content"]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")

        # 7) Сохраняем в базу: сначала вопрос пользователя
        await add_message(
            chat.id,
            role=MessageRole.USER,
            content=prompt,
            prompt_tokens=prompt_tokens,
            total_tokens=prompt_tokens,
        )

        # потом ответ бота
        await add_message(
            chat.id,
            role=MessageRole.BOT,
            content=response_text,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        # 8) Возвращаем текст ответа
        return response_text

    async def create_embedding(self, text: str, model_key: str) -> List[float]:
        """
        Запрос эмбеддинга для текста. Возвращает список чисел.
        """
        model = await get_model_by_key(model_key)
        if not model:
            raise RuntimeError(f"Модель embedding '{model_key}' не найдена.")
        payload = {"model": model.model_id, "input": text, "encoding_format": "float"}
        data = await self._request("POST", "/embeddings", json=payload)
        return data["data"][0]["embedding"]

    async def run_workflow(self, text: str, agent_names: List[str], args: Dict) -> Dict:
        """
        Запускает workflow-агентов. Возвращает JSON с полем 'result'.
        """
        payload = {"text": text, "agent_names": agent_names, "args": args}
        data = await self._request("POST", "/workflows/run", json=payload)
        return data.get("result", {})

    async def analyze_image(
            self,
            user_id: int,
            image_url: str,
            prompt: Optional[str] = None
    ) -> str:
        """
        Отправляет URL изображения в vision-модель активного чата и возвращает
        её развернутый анализ: описание, решение задач и уточняющие вопросы.
        `prompt` — дополнительный текст от пользователя (например, подпись к фото).
        """
        # 1) Находим активный чат по user_id
        chat = await get_active_chat(user_id)
        if not chat:
            raise RuntimeError("Нет активного разговора.")

        # 2) Проверяем, что выбранная модель поддерживает vision
        model = await get_model_by_key(chat.model_key)
        model_id: str = model.model_id  # type: ignore[assignment]
        if not model or "vision" not in model_id.lower():
            raise RuntimeError("Текущая модель не поддерживает анализ изображений.")

        # 3) Системная роль с чёткой инструкцией по vision-анализу
        system = {
            "role": "system",
            "content": (
                "You are VisionGPT (aka Luch Neuro), an expert AI vision assistant.\n"
                "When the user sends an image, you must:\n"
                "1. Describe in Russian everything you see, using clear bullet points.\n"
                "2. If the image contains any visible problem, question or exercise, "
                "   identify it and solve it step by step with your reasoning.\n"
                "3. If any part is unreadable or ambiguous, ask the user for clarification.\n"
                "4. Be thorough, accurate and concise."
            )
        }

        # 4) Собираем только пользовательский текст (если есть) и URL изображения
        text_part = prompt.strip() if prompt else ""
        user_msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": text_part},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }

        # 5) Собираем и отправляем payload
        payload = {
            "model": model_id,
            "messages": [system, user_msg],
            "max_tokens": 2560,
            "temperature": 0.2
        }
        data = await self._request(
            "POST",
            "/chat/completions",
            json=payload,
            timeout=120
        )

        # 6) Извлечь ответ и статистику токенов
        resp = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")

        # 7) Сохраняем компактный плейсхолдер, чтобы не переполнять колонку
        placeholder = "[Image]" if image_url.startswith("data:") else f"[Image] {image_url}"
        await add_message(
            chat.id,
            role=MessageRole.USER,
            content=placeholder,
            prompt_tokens=prompt_tokens,
            total_tokens=prompt_tokens,
        )
        await add_message(
            chat.id,
            role=MessageRole.BOT,
            content=resp,
            completion_tokens=completion_tokens,
            total_tokens=completion_tokens,
        )

        return resp

    async def analyze_image_bytes(
            self,
            user_id: int,
            image_bytes: bytes,
            prompt: Optional[str] = None
    ) -> str:
        """
        Принимает байты изображения и передаёт их в виде data-URI,
        не создавая никаких временных файлов.
        """
        import base64
        import imghdr

        # Определяем MIME-тип по сигнатуре файла (fallback — image/jpeg)
        img_type = imghdr.what(None, h=image_bytes) or "jpeg"
        mime = f"image/{img_type}"

        # Формируем data-URI
        b64 = base64.b64encode(image_bytes).decode()
        data_uri = f"data:{mime};base64,{b64}"

        # Отправляем сразу в analyze_image
        return await self.analyze_image(user_id, data_uri, prompt)

    async def close(self):
        """Закрываем aiohttp-сессию."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "AIService":
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
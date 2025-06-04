# web/app.py
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from config import ALLOWED_ORIGINS
import logging

# Скрываем отладочные сообщения multipart
logging.getLogger("python_multipart.multipart").setLevel(logging.INFO)

BASE_DIR = Path(__file__).resolve().parent

# Если ALLOWED_ORIGINS == ["*"], нельзя одновременно allow_credentials=True
use_credentials = True
if ALLOWED_ORIGINS == ["*"]:
    use_credentials = False

middleware = [
    Middleware(
        CORSMiddleware, # type: ignore[arg-type]
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=use_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
]

app = FastAPI(
    title="Luch Neuro Web",
    version="0.1.0",
    description="Веб-клиент Luch Neuro (тот же API, что и Telegram-бот)",
    middleware=middleware,
)

# ───── Статика ─────
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

# ───── Cache-Control для статики ─────
@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=86400, immutable"
    return response

# ───── Шаблоны ─────
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ───── Подключаем API-роуты ─────
from web.routes import router as api_router  # noqa: E402
app.include_router(api_router)

# ───── SPA: отдаём index.html на все пути ─────
@app.get(
    "/",
    response_class=HTMLResponse,
    summary="Главная точка входа SPA",
)
async def root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Luch Neuro Web"},
    )

@app.get(
    "/{_full_path:path}",
    response_class=HTMLResponse,
    summary="SPA-шаблон для всех пользовательских маршрутов",
)
async def spa(request: Request, _full_path: str):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Luch Neuro Web"},
    )

if __name__ == "__main__":
    uvicorn.run(
        "web.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
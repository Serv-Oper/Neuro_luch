from dotenv import load_dotenv
from pathlib import Path
import os
import sys

# ─────────── Load .env ───────────
dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# ─────────── Skip validation in testing mode ───────────
if not os.getenv("TESTING"):
    # ─────────── Validate critical environment variables ───────────
    required_vars = {
        "BOT_TOKEN": os.getenv("BOT_TOKEN"),
        "IO_API_KEY": os.getenv("IO_API_KEY"),
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
        "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
        "REGISTER_URL": os.getenv("REGISTER_URL"),
        "GOOGLE_REDIRECT_URI": os.getenv("GOOGLE_REDIRECT_URI"),
    }
    missing = [name for name, val in required_vars.items() if not val]
    if missing:
        sys.stderr.write(
            f"Error: the following environment variables must be set: {', '.join(missing)}\n"
        )
        sys.exit(1)

# ───────────  Telegram & AI ───────────
BOT_TOKEN         = os.getenv("BOT_TOKEN")
IO_API_KEY        = os.getenv("IO_API_KEY")

JWT_SECRET_KEY    = os.getenv("JWT_SECRET_KEY")

# ────────── CORS ──────────
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
if allowed_origins_env:
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in allowed_origins_env.split(",")
        if origin.strip()
    ]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:63342",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:4200",
        "https://3985-2a09-bac5-48a1-505-00-80-183.ngrok-free.app",
        "https://jocular-douhua-c28ae0.netlify.app",
    ]

FREE_DAILY_LIMIT   = int(os.getenv("FREE_DAILY_LIMIT", 5))
FREE_CHAT_LIMIT    = int(os.getenv("FREE_CHAT_LIMIT", 5))
PREMIUM_CHAT_LIMIT = int(os.getenv("PREMIUM_CHAT_LIMIT", 60))

# максимальное (не сбрасывающееся) число обращений гостя к ИИ
GUEST_TOTAL_LIMIT  = int(os.getenv("GUEST_TOTAL_LIMIT", 3))

SUPPORT_USERNAME   = os.getenv("SUPPORT_USERNAME", "YourSupport")
CONFIRM_CODE_EXP_MIN = int(os.getenv("CONFIRM_CODE_EXP_MIN", 15))

MODELS = {
    "fast":   "microsoft/phi-4",
    "smart":  "deepseek-ai/DeepSeek-R1",
    "vision": "meta-llama/Llama-3.2-90B-Vision-Instruct",
}

# ───────────  Database ───────────
DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT")
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME")

# ───────────  Email Confirmation ───────────
EMAIL_FROM    = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD= os.getenv("EMAIL_PASSWORD")
SMTP_SERVER   = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))

# ───────────  URL регистрации, который показывает бот ───────────
REGISTER_URL         = os.getenv("REGISTER_URL")

# ───────────  Google OAuth ───────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# тот же URI, что в Google Console в Authorized redirect URIs
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI")
load_dotenv()
# ───────────  Окружение ───────────
ENV = os.getenv("ENV", "dev")
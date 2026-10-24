import os
import secrets
from dotenv import load_dotenv
load_dotenv()

# Локальный PostgreSQL (docker-compose) — резервный вариант Neon, если переменная DATABASE_URL не задана
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("LOCAL_DB_URL", "postgresql://oleg@/sst_monitoring?host=/var/run/postgresql")
)
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_urlsafe(32)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
GEE_PROJECT_ID = os.getenv("GEE_PROJECT_ID", "")

# Nixtla TimeGPT API
NIXTLA_API_KEY = os.getenv("NIXTLA_API_KEY", "")

# GigaChat (Сбер LLM) — резервный вариант, если ключ Anthropic не задан
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID", "")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET", "")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

# Anthropic Claude Haiku — основной AI бэкенд (отображается как "GigaChat" в UI)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Google Gemini Flash Lite — основной AI бэкенд
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Сетевой ресурс GFS SMB (локальная сеть)
GFS_SMB_HOST = os.getenv("GFS_SMB_HOST", "10.11.60.25")
GFS_SMB_SHARE = os.getenv("GFS_SMB_SHARE", "meteo")
GFS_SMB_USER = os.getenv("GFS_SMB_USER", "")
GFS_SMB_PASS = os.getenv("GFS_SMB_PASS", "")
GFS_SMB_DOMAIN = os.getenv("GFS_SMB_DOMAIN", "")
GFS_SMB_BASE = os.getenv(
    "GFS_SMB_BASE",
    "data/NOAA/NCEP/FTPPRD/pub/data/nccf/com/gfs/prod0p25.sfc",
)

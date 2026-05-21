import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str           = os.getenv("TELEGRAM_BOT_TOKEN", "")
CLAUDE_API_KEY: str      = os.getenv("CLAUDE_API_KEY", "")
MAX_IMAGES_PER_HOUR: int = int(os.getenv("MAX_IMAGES_PER_HOUR", "5"))
CLAUDE_MODEL: str        = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

MAX_TOKENS: int          = 2500    # 2500 produces complete prompts, ~30% faster than 3500
CLAUDE_TIMEOUT: float    = 120.0   # Railway has no hard process limit — 120s covers all cases

MAX_IMAGE_BYTES: int     = 5 * 1024 * 1024   # 5 MB — Claude hard limit
TELEGRAM_MSG_LIMIT: int  = 4000              # Telegram cap is 4096, safe margin

SUPPORTED_MIME_TYPES: dict[str, str] = {
    "image/jpeg": "image/jpeg",
    "image/jpg":  "image/jpeg",
    "image/png":  "image/png",
    "image/webp": "image/webp",
    "image/gif":  "image/gif",
}

if not BOT_TOKEN:
    raise EnvironmentError("TELEGRAM_BOT_TOKEN is not set")
if not CLAUDE_API_KEY:
    raise EnvironmentError("CLAUDE_API_KEY is not set")

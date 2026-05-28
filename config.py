import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN: str          = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Admin identifier — accepts numeric ID OR @username
# Examples: "123456789"  OR  "@forca91"  OR  "forca91"
ADMIN_IDENTIFIER: str   = os.getenv("ADMIN_USER_ID", "").strip().lstrip("@")

# ── Claude API ────────────────────────────────────────────────────────────────
CLAUDE_API_KEY: str     = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL: str       = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
MAX_TOKENS: int         = 2500
CLAUDE_TIMEOUT: float   = 120.0

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str       = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str       = os.getenv("SUPABASE_ANON_KEY", "")
DB_ENABLED: bool        = bool(SUPABASE_URL and SUPABASE_KEY)

# ── Rate limiting ─────────────────────────────────────────────────────────────
MAX_IMAGES_PER_HOUR: int = int(os.getenv("MAX_IMAGES_PER_HOUR", "5"))

# ── Telegram limits ───────────────────────────────────────────────────────────
MAX_IMAGE_BYTES: int    = 5 * 1024 * 1024
TELEGRAM_MSG_LIMIT: int = 4000

SUPPORTED_MIME_TYPES: dict[str, str] = {
    "image/jpeg": "image/jpeg",
    "image/jpg":  "image/jpeg",
    "image/png":  "image/png",
    "image/webp": "image/webp",
    "image/gif":  "image/gif",
}

# ── Validation ────────────────────────────────────────────────────────────────
if not BOT_TOKEN:
    raise EnvironmentError("TELEGRAM_BOT_TOKEN is not set")
if not CLAUDE_API_KEY:
    raise EnvironmentError("CLAUDE_API_KEY is not set")

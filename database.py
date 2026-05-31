"""
database.py — Supabase integration for Image Quality Bot v1.5
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from config import SUPABASE_URL, SUPABASE_KEY, DB_ENABLED, MAX_IMAGES_PER_HOUR

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def _today_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _one_hour_ago_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


def _safe_count(result) -> int:
    """Extract row count from Supabase result — compatible with v1.x and v2.x."""
    if hasattr(result, "count") and result.count is not None:
        return int(result.count)
    if hasattr(result, "data") and result.data is not None:
        return len(result.data)
    return 0


# ── Connection check ──────────────────────────────────────────────────────────

async def check_connection() -> Tuple[bool, str]:
    """
    Test the Supabase connection step by step.
    Returns (success: bool, message: str) — the message is shown to admin.
    """
    if not DB_ENABLED:
        parts = []
        if not SUPABASE_URL:
            parts.append("SUPABASE_URL مفقود")
        if not SUPABASE_KEY:
            parts.append("SUPABASE_ANON_KEY مفقود")
        return False, "متغيرات غير موجودة: " + " | ".join(parts)

    def _sync() -> Tuple[bool, str]:
        # Step 1: Create client
        try:
            client = _get_client()
        except Exception as e:
            return False, f"فشل إنشاء الـ client:\n{type(e).__name__}: {e}"

        # Step 2: Query users table
        try:
            result = client.table("users").select("user_id", count="exact").limit(1).execute()
            users_count = _safe_count(result)
            return True, f"الاتصال ناجح ✅\nجدول users: {users_count} سجل"
        except Exception as e:
            return False, (
                f"الـ client يعمل لكن الاستعلام فشل:\n"
                f"{type(e).__name__}: {e}\n\n"
                f"تحقق من:\n"
                f"• تشغيل schema.sql في Supabase → SQL Editor\n"
                f"• صلاحيات anon key على الجداول"
            )

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        return False, f"خطأ غير متوقع: {type(e).__name__}: {e}"


# ── Write operations ──────────────────────────────────────────────────────────

async def register_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
) -> None:
    if not DB_ENABLED:
        return

    def _sync():
        _get_client().table("users").upsert(
            {
                "user_id":    user_id,
                "username":   username or "",
                "first_name": first_name or "",
            },
            on_conflict="user_id",
        ).execute()

    try:
        await asyncio.to_thread(_sync)
    except Exception as e:
        logger.warning(f"register_user({user_id}) failed: {type(e).__name__}: {e}")


async def log_request(
    user_id: int,
    request_type: str,
    success: bool,
    response_time_ms: int,
) -> None:
    if not DB_ENABLED:
        return

    def _sync():
        _get_client().table("requests").insert(
            {
                "user_id":          user_id,
                "request_type":     request_type,
                "success":          success,
                "response_time_ms": response_time_ms,
            }
        ).execute()

    try:
        await asyncio.to_thread(_sync)
    except Exception as e:
        logger.warning(f"log_request({user_id}) failed: {type(e).__name__}: {e}")


# ── Rate limiting ─────────────────────────────────────────────────────────────

async def count_recent_requests(user_id: int) -> Optional[int]:
    """Count successful requests in the last hour. Returns None if DB unavailable."""
    if not DB_ENABLED:
        return None

    def _sync() -> int:
        result = (
            _get_client()
            .table("requests")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("success", True)
            .gte("created_at", _one_hour_ago_iso())
            .execute()
        )
        return _safe_count(result)

    try:
        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.warning(f"count_recent_requests({user_id}) failed: {e}")
        return None


# ── Stats ─────────────────────────────────────────────────────────────────────

async def get_stats() -> Optional[dict]:
    """Fetch all statistics. Returns None if DB unavailable or query fails."""
    if not DB_ENABLED:
        return None

    def _sync() -> dict:
        c     = _get_client()
        today = _today_iso()

        def q_count(table: str, **eq_filters) -> int:
            query = c.table(table).select("*", count="exact")
            for col, val in eq_filters.items():
                if col.startswith("gte__"):
                    query = query.gte(col[5:], val)
                else:
                    query = query.eq(col, val)
            return _safe_count(query.execute())

        total_users  = q_count("users")
        today_users  = q_count("users",    gte__joined_at=today)
        total_req    = q_count("requests")
        today_req    = q_count("requests", gte__created_at=today)
        success_req  = q_count("requests", success=True)
        analyze_req  = q_count("requests", request_type="analyze")
        patch_req    = q_count("requests", request_type="patch")

        # Average response time (ms → seconds)
        times_result = (
            c.table("requests")
            .select("response_time_ms")
            .eq("success", True)
            .execute()
        )
        times = [
            r["response_time_ms"]
            for r in (times_result.data or [])
            if r.get("response_time_ms") is not None
        ]
        avg_ms = int(sum(times) / len(times)) if times else 0

        return {
            "total_users":   total_users,
            "today_users":   today_users,
            "total_req":     total_req,
            "today_req":     today_req,
            "success_rate":  round(success_req / total_req * 100) if total_req else 0,
            "avg_seconds":   round(avg_ms / 1000),
            "analyze_count": analyze_req,
            "patch_count":   patch_req,
        }

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.error(f"get_stats failed: {type(exc).__name__}: {exc}", exc_info=True)
        return None

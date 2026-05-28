"""
database.py — Supabase integration for Image Quality Bot v1.5

Handles:
  - User registration (upsert on every interaction)
  - Request logging (for stats and DB-backed rate limiting)
  - Rate limit checking (persistent across restarts)
  - Admin statistics

All operations fail OPEN — if Supabase is unreachable the bot
keeps working using the in-memory fallback in rate_limiter.py.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from config import SUPABASE_URL, SUPABASE_KEY, DB_ENABLED, MAX_IMAGES_PER_HOUR

logger = logging.getLogger(__name__)

# ── Client ────────────────────────────────────────────────────────────────────

_client = None


def _get_client():
    """Return a cached Supabase sync client."""
    global _client
    if _client is None:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _one_hour_ago_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


def _today_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


# ── Public async API ──────────────────────────────────────────────────────────

async def register_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
) -> None:
    """Upsert user record. Silent on failure."""
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
    except Exception as exc:
        logger.warning(f"register_user failed for {user_id}: {exc}")


async def log_request(
    user_id: int,
    request_type: str,    # 'analyze' | 'patch'
    success: bool,
    response_time_ms: int,
) -> None:
    """Insert one request record. Silent on failure."""
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
    except Exception as exc:
        logger.warning(f"log_request failed for {user_id}: {exc}")


async def count_recent_requests(user_id: int) -> Optional[int]:
    """
    Count successful requests for a user in the last hour.
    Returns None if DB unavailable (caller should use in-memory fallback).
    """
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
        return result.count or 0
    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.warning(f"count_recent_requests failed for {user_id}: {exc}")
        return None


async def get_stats() -> Optional[dict]:
    """
    Collect all statistics for the /stats admin command.
    Returns None if DB unavailable.
    """
    if not DB_ENABLED:
        return None

    def _sync() -> dict:
        client = _get_client()
        today  = _today_start_iso()

        total_users   = client.table("users").select("user_id", count="exact").execute().count or 0
        today_users   = client.table("users").select("user_id", count="exact").gte("joined_at", today).execute().count or 0

        total_req     = client.table("requests").select("id", count="exact").execute().count or 0
        today_req     = client.table("requests").select("id", count="exact").gte("created_at", today).execute().count or 0

        success_req   = client.table("requests").select("id", count="exact").eq("success", True).execute().count or 0
        analyze_req   = client.table("requests").select("id", count="exact").eq("request_type", "analyze").execute().count or 0
        patch_req     = client.table("requests").select("id", count="exact").eq("request_type", "patch").execute().count or 0

        # Average response time (successful requests only)
        times_result  = (
            client.table("requests")
            .select("response_time_ms")
            .eq("success", True)
            .not_.is_("response_time_ms", "null")
            .execute()
        )
        times = [r["response_time_ms"] for r in times_result.data if r.get("response_time_ms")]
        avg_ms = int(sum(times) / len(times)) if times else 0

        success_rate  = round(success_req / total_req * 100) if total_req else 0

        return {
            "total_users":   total_users,
            "today_users":   today_users,
            "total_req":     total_req,
            "today_req":     today_req,
            "success_rate":  success_rate,
            "avg_seconds":   round(avg_ms / 1000),
            "analyze_count": analyze_req,
            "patch_count":   patch_req,
        }

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.error(f"get_stats failed: {exc}")
        return None

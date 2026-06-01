"""
database.py — Supabase integration via direct REST API calls (httpx)

Uses httpx directly instead of supabase-py to avoid version conflicts.
Supabase exposes a PostgREST API at {SUPABASE_URL}/rest/v1/{table}.
All operations are fully async — no asyncio.to_thread needed.
"""

import asyncio
import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from config import SUPABASE_URL, SUPABASE_KEY, DB_ENABLED, MAX_IMAGES_PER_HOUR

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_BASE = f"{SUPABASE_URL.rstrip('/')}/rest/v1" if SUPABASE_URL else ""

_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

_TIMEOUT = httpx.Timeout(15.0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _today_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _one_hour_ago_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


def _parse_count(response: httpx.Response) -> int:
    """
    Extract total count from PostgREST Content-Range header.
    Header format: "0-9/42"  or  "*/42"
    Falls back to len(data) if header is missing.
    """
    cr = response.headers.get("content-range", "")
    if "/" in cr:
        right = cr.split("/")[-1]
        if right.isdigit():
            return int(right)
    data = response.json()
    return len(data) if isinstance(data, list) else 0


async def _count(table: str, filters: dict | None = None) -> int:
    """GET count of rows matching filters using PostgREST."""
    params: dict = {"select": "*", "limit": "0"}
    if filters:
        params.update(filters)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(
            f"{_BASE}/{table}",
            headers={**_HEADERS, "Prefer": "count=exact"},
            params=params,
        )
        r.raise_for_status()
        return _parse_count(r)


# ── Connection check ──────────────────────────────────────────────────────────

async def check_connection() -> Tuple[bool, str]:
    """
    Test the Supabase REST API connection step by step.
    Returns (success, human-readable message).
    """
    if not DB_ENABLED:
        parts = []
        if not SUPABASE_URL:
            parts.append("SUPABASE_URL مفقود")
        if not SUPABASE_KEY:
            parts.append("SUPABASE_ANON_KEY مفقود")
        return False, "متغيرات غير موجودة:\n" + "\n".join(parts)

    try:
        count = await _count("users")
        return True, f"الاتصال ناجح ✅\nجدول users: {count} مستخدم"

    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code == 401:
            return False, (
                "خطأ مصادقة (401)\n\n"
                "SUPABASE_ANON_KEY غير صحيح.\n"
                "انسخه من: Supabase → Settings → API → anon public"
            )
        if code == 404:
            return False, (
                "جدول users غير موجود (404)\n\n"
                "شغّل ملف schema.sql في:\n"
                "Supabase → SQL Editor → New query → Run"
            )
        return False, f"HTTP {code}:\n{e.response.text[:300]}"

    except httpx.ConnectError:
        return False, (
            f"تعذّر الاتصال بـ Supabase\n\n"
            f"تحقق من SUPABASE_URL:\n{SUPABASE_URL}"
        )

    except httpx.TimeoutException:
        return False, "انتهت مهلة الاتصال (timeout)\nتحقق من اتصال الإنترنت على Railway"

    except Exception as e:
        return False, f"{type(e).__name__}:\n{e}"


# ── Write operations ──────────────────────────────────────────────────────────

async def register_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
) -> None:
    """Upsert user record. Silent on failure."""
    if not DB_ENABLED:
        return
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{_BASE}/users",
                headers={**_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json={
                    "user_id":    user_id,
                    "username":   username or "",
                    "first_name": first_name or "",
                },
            )
            r.raise_for_status()
    except Exception as e:
        logger.warning(f"register_user({user_id}) failed: {type(e).__name__}: {e}")


async def log_request(
    user_id: int,
    request_type: str,
    success: bool,
    response_time_ms: int,
) -> None:
    """Insert one request record. Silent on failure."""
    if not DB_ENABLED:
        return
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{_BASE}/requests",
                headers={**_HEADERS, "Prefer": "return=minimal"},
                json={
                    "user_id":          user_id,
                    "request_type":     request_type,
                    "success":          success,
                    "response_time_ms": response_time_ms,
                },
            )
            r.raise_for_status()
    except Exception as e:
        logger.warning(f"log_request({user_id}) failed: {type(e).__name__}: {e}")


# ── Rate limiting ─────────────────────────────────────────────────────────────

async def count_recent_requests(user_id: int) -> Optional[int]:
    """Count successful requests in the last hour. Returns None if unavailable."""
    if not DB_ENABLED:
        return None
    try:
        return await _count("requests", {
            "user_id":    f"eq.{user_id}",
            "success":    "eq.true",
            "created_at": f"gte.{_one_hour_ago_iso()}",
        })
    except Exception as e:
        logger.warning(f"count_recent_requests({user_id}) failed: {e}")
        return None


# ── Statistics ────────────────────────────────────────────────────────────────

async def get_stats() -> Optional[dict]:
    """Fetch all stats concurrently. Returns None on failure."""
    if not DB_ENABLED:
        return None

    try:
        today = _today_iso()

        # Run all count queries concurrently
        (
            total_users, today_users,
            total_req, today_req,
            success_req, analyze_req, patch_req,
        ) = await asyncio.gather(
            _count("users"),
            _count("users",    {"joined_at":    f"gte.{today}"}),
            _count("requests"),
            _count("requests", {"created_at":   f"gte.{today}"}),
            _count("requests", {"success":      "eq.true"}),
            _count("requests", {"request_type": "eq.analyze"}),
            _count("requests", {"request_type": "eq.patch"}),
        )

        # Average response time
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(
                f"{_BASE}/requests",
                headers=_HEADERS,
                params={"select": "response_time_ms", "success": "eq.true"},
            )
            r.raise_for_status()
            times = [
                row["response_time_ms"]
                for row in r.json()
                if row.get("response_time_ms") is not None
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

    except Exception as exc:
        logger.error(f"get_stats failed: {type(exc).__name__}: {exc}", exc_info=True)
        return None

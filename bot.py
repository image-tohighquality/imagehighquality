"""
bot.py — Main entry point for Railway deployment.
Uses long-polling. python-telegram-bot v20 handles reconnection
and graceful shutdown automatically.
"""

import io
import base64
import asyncio
import contextlib
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

import messages as msg
from config import (
    BOT_TOKEN,
    MAX_IMAGES_PER_HOUR,
    MAX_IMAGE_BYTES,
    TELEGRAM_MSG_LIMIT,
    SUPPORTED_MIME_TYPES,
)
from rate_limiter import limiter
from claude_client import analyze_image, generate_patch
from subscription import is_member, join_keyboard, CHANNEL_URL

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# ── Patch detection keywords ──────────────────────────────────────────────────
PATCH_KEYWORDS = {
    "مشكلة", "خاطئ", "سيء", "غلط", "تغير", "اصلح", "فشل", "رديء",
    "fix", "problem", "wrong", "bad", "failed", "patch", "incorrect",
}


# ── Subscription gate ─────────────────────────────────────────────────────────

async def _check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Verify the user is subscribed to the required channel.
    Sends a join prompt and returns False if not subscribed.
    Returns True if subscribed (or check fails gracefully).
    """
    user_id = update.effective_user.id

    if await is_member(context.bot, user_id):
        return True

    # Send subscription prompt
    await update.effective_message.reply_text(
        msg.NOT_SUBSCRIBED,
        reply_markup=join_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return False


# ── Progress updater ──────────────────────────────────────────────────────────

async def _progress_updater(status_msg, steps: list[tuple[int, str]]) -> None:
    """
    Send timed status edits while a long operation runs.
    steps: list of (delay_seconds, message_text).
    Designed to run as an asyncio.Task and be cancelled when done.
    """
    for delay, text in steps:
        await asyncio.sleep(delay)
        with contextlib.suppress(Exception):
            await status_msg.edit_text(text, parse_mode=ParseMode.HTML)


# ── Download helpers ──────────────────────────────────────────────────────────

async def _download_photo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> tuple[str, str] | None:
    """Download highest-resolution Telegram photo. Returns (base64, mime_type) or None."""
    photo = update.message.photo[-1]

    if photo.file_size and photo.file_size > MAX_IMAGE_BYTES:
        await update.message.reply_text(msg.IMAGE_TOO_LARGE)
        return None

    tg_file = await context.bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"


async def _download_document(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> tuple[str, str] | None:
    """Download image sent as uncompressed file. Returns (base64, mime_type) or None."""
    doc = update.message.document
    mime = (doc.mime_type or "").lower()

    if mime not in SUPPORTED_MIME_TYPES:
        await update.message.reply_text(msg.UNSUPPORTED_FILE, parse_mode=ParseMode.HTML)
        return None

    if doc.file_size and doc.file_size > MAX_IMAGE_BYTES:
        await update.message.reply_text(msg.IMAGE_TOO_LARGE)
        return None

    tg_file = await context.bot.get_file(doc.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), SUPPORTED_MIME_TYPES[mime]


# ── Message splitter ──────────────────────────────────────────────────────────

async def _send_long(update: Update, text: str) -> None:
    """Split and send messages exceeding Telegram's 4096-character limit."""
    if len(text) <= TELEGRAM_MSG_LIMIT:
        await update.message.reply_text(text)
        return

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= TELEGRAM_MSG_LIMIT:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, TELEGRAM_MSG_LIMIT)
        if split_at == -1:
            split_at = TELEGRAM_MSG_LIMIT
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")

    for i, chunk in enumerate(chunks):
        prefix = f"({i + 1}/{len(chunks)})\n" if len(chunks) > 1 else ""
        await update.message.reply_text(prefix + chunk)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show welcome message — only after subscription is confirmed."""
    if not await _check_subscription(update, context):
        return
    await update.message.reply_text(msg.WELCOME, parse_mode=ParseMode.HTML)


async def handle_verify_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback fired when user taps 'اشتركت — تحقق' button."""
    query = update.callback_query
    await query.answer()  # dismiss the loading indicator on the button

    user_id = update.effective_user.id
    subscribed = await is_member(context.bot, user_id)

    if subscribed:
        # Replace the subscription prompt with a success message
        await query.edit_message_text(
            msg.SUBSCRIPTION_VERIFIED,
            parse_mode=ParseMode.HTML,
        )
        # Then send the full welcome message as a new message
        await context.bot.send_message(
            chat_id=user_id,
            text=msg.WELCOME,
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"User {user_id} subscription verified successfully")
    else:
        # Alert without closing the prompt
        await query.answer(
            "❌ لم يتم الاشتراك بعد. انضم للقناة أولاً ثم اضغط تحقق.",
            show_alert=True,
        )


def _is_patch_request(caption: str) -> bool:
    if not caption:
        return False
    lower = caption.lower()
    return caption.strip().startswith("/fix") or any(k in lower for k in PATCH_KEYWORDS)


async def _process_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    download_fn,
) -> None:
    """Shared logic for photo and document handlers."""
    # ── Subscription gate ──
    if not await _check_subscription(update, context):
        return

    user_id = update.effective_user.id
    caption = (update.message.caption or "").strip()

    # ── Rate limit ──
    if not limiter.is_allowed(user_id):
        secs = limiter.seconds_until_reset(user_id)
        minutes = max(1, secs // 60)
        await update.message.reply_text(
            msg.RATE_LIMITED.format(limit=MAX_IMAGES_PER_HOUR, minutes=minutes)
        )
        return

    is_patch = _is_patch_request(caption)
    status_text = msg.PATCH_MODE_DETECTED if is_patch else msg.ANALYZING
    status = await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

    # ── Progress updates ──
    progress_task = asyncio.create_task(
        _progress_updater(status, [
            (30, msg.ANALYZING_LONG),
            (30, msg.ANALYZING_FINISH),  # 30 + 30 = 60 s
        ])
    )

    try:
        image_data = await download_fn(update, context)
        if image_data is None:
            progress_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await progress_task
            await status.delete()
            return

        b64, mime = image_data

        if is_patch:
            problem = caption.replace("/fix", "").strip() or "مشكلة غير محددة"
            response = await generate_patch(b64, problem, mime)
        else:
            response = await analyze_image(b64, mime)

        logger.info(f"user={user_id} patch={is_patch} chars={len(response)}")

        progress_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await progress_task
        await status.delete()
        await _send_long(update, response)

    except ValueError:
        progress_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await progress_task
        await status.edit_text(msg.ERROR_IMAGE_UNREADABLE)

    except TimeoutError:
        progress_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await progress_task
        await status.edit_text(msg.ERROR_TIMEOUT)

    except Exception as e:
        progress_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await progress_task
        logger.error(f"Unexpected error user={user_id}: {e}", exc_info=True)
        await status.edit_text(msg.ERROR_GENERIC)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _process_image(update, context, _download_photo)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _process_image(update, context, _download_document)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    if text.startswith("/"):
        return
    if not await _check_subscription(update, context):
        return
    await update.message.reply_text(msg.NO_PHOTO, parse_mode=ParseMode.HTML)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Unhandled PTB error: {context.error}", exc_info=context.error)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("Starting Image Quality Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))

    # Subscription callback
    app.add_handler(CallbackQueryHandler(handle_verify_subscription, pattern="^verify_sub$"))

    # Media handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))

    # Text fallback
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_error_handler(error_handler)

    logger.info("Bot is running. Polling for updates...")

    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )

    logger.info("Bot stopped.")


if __name__ == "__main__":
    main()

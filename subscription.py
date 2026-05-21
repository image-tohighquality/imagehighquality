"""
subscription.py — Channel membership gate.

Checks whether a user is subscribed to the required Telegram channel
before allowing access to the bot's features.

IMPORTANT: The bot must be added as an ADMIN to @forca91 for
get_chat_member() to work reliably. Without admin rights the API
may raise errors for users who haven't interacted with the bot before.
"""

import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.constants import ChatMemberStatus

logger = logging.getLogger(__name__)

CHANNEL_USERNAME: str = "@forca91"
CHANNEL_URL: str      = "https://t.me/forca91"


async def is_member(bot: Bot, user_id: int) -> bool:
    """
    Return True if the user is an active member of CHANNEL_USERNAME.
    Fails OPEN on any error (bot not admin, network issue, etc.)
    so legitimate users are never permanently blocked by a check failure.
    """
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id,
        )
        status = member.status

        if status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
        ):
            return True

        # RESTRICTED users may still be able to read the channel
        if status == ChatMemberStatus.RESTRICTED:
            return bool(getattr(member, "is_member", False))

        # LEFT or BANNED
        return False

    except TelegramError as exc:
        logger.warning(
            f"Subscription check failed for user {user_id}: {exc} — "
            "failing open to avoid blocking legitimate users."
        )
        return True


def join_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard with a join button and a verify button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 انضم للقناة الآن", url=CHANNEL_URL)],
        [InlineKeyboardButton("✅ اشتركت — تحقق", callback_data="verify_sub")],
    ])

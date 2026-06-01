import asyncio
import logging
import anthropic
from config import CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, CLAUDE_TIMEOUT
from system_prompt import SYSTEM_PROMPT, PATCH_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client = anthropic.AsyncAnthropic(
    api_key=CLAUDE_API_KEY,
    timeout=CLAUDE_TIMEOUT,
)


async def analyze_image(image_b64: str, mime_type: str = "image/jpeg") -> str:
    """
    Send image to Claude with skill v4 system prompt.
    Returns the complete restoration prompt as a string.
    """
    try:
        response = await _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "حلل هذه الصورة وأنتج البرومبت الاحترافي الكامل المخصص لها.",
                        },
                    ],
                }
            ],
        )
        text = _extract_text(response)
        logger.info(f"analyze_image completed: {len(text)} chars")
        return text

    except anthropic.RateLimitError:
        logger.warning("Claude API rate limit reached")
        return "⚠️ الطلبات على الذكاء الاصطناعي كثيرة حالياً. انتظر دقيقة واحدة ثم أعد الإرسال."

    except anthropic.BadRequestError as e:
        logger.error(f"Claude rejected the image: {e}")
        raise ValueError("IMAGE_UNREADABLE")

    except (anthropic.APITimeoutError, asyncio.TimeoutError):
        logger.error(f"Claude API timed out after {CLAUDE_TIMEOUT}s")
        raise TimeoutError("Claude API timeout")

    except anthropic.APIConnectionError as e:
        logger.error(f"Claude connection error: {e}")
        raise

    except anthropic.APIError as e:
        logger.error(f"Claude API error [{e.status_code}]: {e}")
        raise


async def generate_patch(
    image_b64: str,
    problem_description: str,
    mime_type: str = "image/jpeg",
) -> str:
    """Analyze a failed result and generate a targeted patch prompt."""
    try:
        response = await _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            system=PATCH_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                f"هذه الصورة هي الناتج الذي فشل.\n"
                                f"المشكلة: {problem_description}\n"
                                f"أعطني patch prompt مخصص لإصلاحها."
                            ),
                        },
                    ],
                }
            ],
        )
        return _extract_text(response)

    except anthropic.RateLimitError:
        return "⚠️ الطلبات كثيرة حالياً. انتظر دقيقة ثم أعد الإرسال."

    except (anthropic.APITimeoutError, asyncio.TimeoutError):
        raise TimeoutError("Claude API timeout")

    except anthropic.APIError as e:
        logger.error(f"Claude API error in patch: {e}")
        raise


def _extract_text(response: anthropic.types.Message) -> str:
    return "\n".join(
        block.text for block in response.content if hasattr(block, "text")
    ).strip()

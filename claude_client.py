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


# ── Prompt extraction ─────────────────────────────────────────────────────────

def _extract_prompt(text: str) -> str:
    """
    Extract only the English restoration/patch prompt from Claude's full response.

    Primary:   looks for <<<START>>> ... <<<END>>> markers (added to system prompt)
    Secondary: looks for ════ delimiter lines (fallback for edge cases)
    Final:     returns full text as-is so the user always gets something useful
    """
    # ── Primary: explicit markers ──────────────────────────────────────────
    if "<<<START>>>" in text and "<<<END>>>" in text:
        try:
            start = text.index("<<<START>>>") + len("<<<START>>>")
            end   = text.index("<<<END>>>")
            extracted = text[start:end].strip()
            if len(extracted) > 50:                # sanity: must be substantial
                return extracted
        except ValueError:
            pass

    # ── Secondary: ════ boundary lines ────────────────────────────────────
    MARKER = "═" * 15
    lines  = text.splitlines()
    marker_lines = [i for i, l in enumerate(lines) if MARKER in l]
    if len(marker_lines) >= 2:
        extracted = "\n".join(lines[marker_lines[0]:marker_lines[-1] + 1]).strip()
        if len(extracted) > 50:
            return extracted

    # ── Final fallback ─────────────────────────────────────────────────────
    logger.warning("_extract_prompt: markers not found — returning full response")
    return text.strip()


def _raw_text(response: anthropic.types.Message) -> str:
    return "\n".join(
        block.text for block in response.content if hasattr(block, "text")
    ).strip()


# ── Public API ────────────────────────────────────────────────────────────────

async def analyze_image(image_b64: str, mime_type: str = "image/jpeg") -> str:
    """
    Send image to Claude and return ONLY the English restoration prompt.
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
        full_text = _raw_text(response)
        prompt    = _extract_prompt(full_text)
        logger.info(f"analyze_image: full={len(full_text)}c extracted={len(prompt)}c")
        return prompt

    except anthropic.RateLimitError:
        logger.warning("Claude rate limit hit")
        return "⚠️ الطلبات على الذكاء الاصطناعي كثيرة حالياً. انتظر دقيقة واحدة ثم أعد الإرسال."

    except anthropic.BadRequestError as e:
        logger.error(f"Claude bad request: {e}")
        raise ValueError("IMAGE_UNREADABLE")

    except (anthropic.APITimeoutError, asyncio.TimeoutError):
        logger.error(f"Claude timed out after {CLAUDE_TIMEOUT}s")
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
    """
    Analyze a failed result and return ONLY the English patch prompt.
    """
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
        full_text = _raw_text(response)
        prompt    = _extract_prompt(full_text)
        logger.info(f"generate_patch: full={len(full_text)}c extracted={len(prompt)}c")
        return prompt

    except anthropic.RateLimitError:
        return "⚠️ الطلبات كثيرة حالياً. انتظر دقيقة ثم أعد الإرسال."

    except (anthropic.APITimeoutError, asyncio.TimeoutError):
        raise TimeoutError("Claude API timeout")

    except anthropic.APIError as e:
        logger.error(f"Claude API error in patch: {e}")
        raise

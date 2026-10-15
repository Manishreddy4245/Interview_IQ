import asyncio
import logging
import random
import re
from typing import Optional, Dict, Any, List, Tuple
from fastapi import HTTPException, status
import groq
from groq import AsyncGroq
from app.core.config import settings

logger = logging.getLogger("interviewiq.groq")


def sanitize_groq_error_message(exc: groq.APIStatusError) -> str:
    """
    Safely extract and sanitize upstream Groq error details.
    Never exposes API keys, tokens, or candidate personal data.
    """
    raw_message = None
    code = None
    failed_generation = None

    if hasattr(exc, "body") and isinstance(exc.body, dict):
        err = exc.body.get("error", {})
        if isinstance(err, dict):
            raw_message = err.get("message")
            code = err.get("code")
            failed_generation = err.get("failed_generation")

    if not raw_message and hasattr(exc, "message") and exc.message:
        raw_message = str(exc.message)

    if not raw_message:
        raw_message = f"Upstream AI service error (HTTP {exc.status_code})"

    # If code indicates json_validate_failed
    if code == "json_validate_failed" or "json_validate_failed" in str(raw_message):
        if failed_generation and "max completion tokens reached" in str(failed_generation):
            clean_msg = "Model output exceeded token limit before completing valid JSON"
        else:
            clean_msg = "Model generated invalid JSON format"
    else:
        clean_msg = str(raw_message)

    # Redact any sensitive substrings like API keys or auth tokens
    clean_msg = re.sub(r"gsk_[A-Za-z0-9_\-]+", "[REDACTED_API_KEY]", clean_msg)
    clean_msg = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "[REDACTED_TOKEN]", clean_msg)
    if len(clean_msg) > 250:
        clean_msg = clean_msg[:247] + "..."

    return clean_msg


def parse_reset_delay(headers: Dict[str, str], default_delay: float = 1.5) -> float:
    """Parse delay in seconds from Groq rate limit headers."""
    # 1. Check standard Retry-After
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return max(0.5, float(retry_after))
        except ValueError:
            pass

    # 2. Check Groq token reset header (e.g., '134ms', '2.5s', '10s')
    reset_tokens = headers.get("x-ratelimit-reset-tokens")
    if reset_tokens:
        s = reset_tokens.strip().lower()
        if s.endswith("ms"):
            try:
                return max(0.2, float(s[:-2]) / 1000.0)
            except ValueError:
                pass
        elif s.endswith("s"):
            try:
                return max(0.5, float(s[:-1]))
            except ValueError:
                pass

    return default_delay


def is_daily_quota_exhausted(headers: Dict[str, str]) -> bool:
    """Detect if daily request quota (RPD) has been completely exhausted."""
    remaining = headers.get("x-ratelimit-remaining-requests")
    if remaining is not None and remaining.strip() == "0":
        reset_reqs = headers.get("x-ratelimit-reset-requests", "")
        if "h" in reset_reqs or "m" in reset_reqs:
            return True
    return False


class GroqClientManager:
    """
    Centralized Groq API manager with concurrency throttling, bounded exponential
    backoff with jitter, provider header inspection, and safe rate-limit error handling.
    """

    def __init__(self) -> None:
        self._client: Optional[AsyncGroq] = None
        # Limit simultaneous in-flight Groq requests to protect free-tier rate limits
        self._semaphore = asyncio.Semaphore(2)

    def get_client(self, max_retries: int = 0) -> AsyncGroq:
        """
        Return an AsyncGroq client instance with controlled max_retries.
        Fails clearly if GROQ_API_KEY is not set.
        """
        if not settings.is_groq_configured:
            raise RuntimeError(
                "Groq configuration error: GROQ_API_KEY is not set in the environment."
            )
        return AsyncGroq(api_key=settings.GROQ_API_KEY, max_retries=max_retries)

    def check_configuration(self) -> Dict[str, Any]:
        """
        Check if the Groq client is configured with credentials.
        Never outputs the API key value.
        """
        if not settings.is_groq_configured:
            return {
                "configured": False,
                "status": "unconfigured",
                "detail": "GROQ_API_KEY is missing from environment variables.",
            }
        return {
            "configured": True,
            "status": "configured",
            "detail": "GROQ_API_KEY is configured and client is ready.",
        }

    async def execute_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: float = 30.0,
        max_retries: int = 2,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        """
        Execute chat completion with centralized rate-limit handling, bounded backoff,
        adaptive token limits, reasoning configuration, and concurrency protection.
        Returns the raw message content string.
        """
        client = self.get_client(max_retries=0)
        target_model = model or settings.GROQ_MODEL

        effective_reasoning_effort = reasoning_effort
        if effective_reasoning_effort is None:
            model_lower = target_model.lower()
            if any(k in model_lower for k in ["gpt-oss", "qwen"]):
                effective_reasoning_effort = "low"

        current_max_tokens = max_tokens
        current_reasoning_effort = effective_reasoning_effort

        async with self._semaphore:
            last_delay = 1.0
            for attempt in range(max_retries + 1):
                try:
                    kwargs: Dict[str, Any] = {
                        "model": target_model,
                        "messages": messages,
                        "response_format": response_format or {"type": "json_object"},
                        "temperature": temperature,
                        "max_tokens": current_max_tokens,
                        "timeout": timeout,
                    }
                    if current_reasoning_effort:
                        kwargs["reasoning_effort"] = current_reasoning_effort

                    completion = await client.chat.completions.create(**kwargs)
                    content = completion.choices[0].message.content
                    if not content or not content.strip():
                        raise ValueError("Model returned empty response content")
                    return content.strip()

                except groq.RateLimitError as exc:
                    headers = dict(exc.response.headers) if hasattr(exc, "response") and exc.response else {}
                    logger.warning(
                        "Groq rate limit encountered (attempt %d/%d): %s",
                        attempt + 1,
                        max_retries + 1,
                        exc.message if hasattr(exc, "message") else str(exc),
                    )

                    # Check for daily exhaustion
                    if is_daily_quota_exhausted(headers):
                        reset_time = headers.get("x-ratelimit-reset-requests", "unknown time")
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Daily Groq API quota exhausted. Resets in {reset_time}. Please wait or try again later.",
                        ) from exc

                    if attempt < max_retries:
                        delay = parse_reset_delay(headers, default_delay=1.5 * (2 ** attempt))
                        jitter = random.uniform(0.1, 0.4)
                        total_sleep = min(delay + jitter, 5.0)  # Bound sleep to max 5s
                        logger.info("Applying bounded rate-limit backoff: sleeping %.2fs before retry", total_sleep)
                        await asyncio.sleep(total_sleep)
                        last_delay = total_sleep
                    else:
                        retry_sec = int(round(last_delay))
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=(
                                f"Rate limit exceeded: AI service is temporarily rate-limited. Please wait {max(5, retry_sec)} seconds "
                                "before retrying. Your response has not been lost."
                            ),
                        ) from exc

                except groq.APITimeoutError as exc:
                    logger.warning("Groq API request timed out on attempt %d", attempt + 1)
                    if attempt < max_retries:
                        await asyncio.sleep(1.0)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                            detail="AI service request timed out. Please try again.",
                        ) from exc

                except groq.APIConnectionError as exc:
                    logger.warning("Groq connection failed on attempt %d: %s", attempt + 1, type(exc).__name__)
                    if attempt < max_retries:
                        await asyncio.sleep(1.0)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Failed to connect to AI service. Please check network connectivity.",
                        ) from exc

                except groq.APIStatusError as exc:
                    sanitized_detail = sanitize_groq_error_message(exc)
                    logger.error("Groq status error: HTTP %s - %s", exc.status_code, sanitized_detail)

                    # If HTTP 400 is due to unsupported reasoning_effort parameter, retry without it
                    if exc.status_code == 400 and current_reasoning_effort and "reasoning_effort" in str(exc.body or ""):
                        logger.info("Retrying without reasoning_effort parameter on model %s", target_model)
                        current_reasoning_effort = None
                        if attempt < max_retries:
                            continue

                    # If HTTP 400 is due to token limit truncation during JSON generation and we have retries left
                    if (
                        exc.status_code == 400
                        and attempt < max_retries
                        and ("max completion tokens reached" in str(exc.body or "") or "json_validate_failed" in str(exc.body or ""))
                    ):
                        current_max_tokens = min(current_max_tokens * 2, 4096)
                        current_reasoning_effort = "low"
                        logger.info("Retrying with increased max_tokens=%d and reasoning_effort=low", current_max_tokens)
                        await asyncio.sleep(0.5)
                        continue

                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"AI service error (HTTP {exc.status_code}): {sanitized_detail}",
                    ) from exc

    async def execute_audio_transcription(
        self,
        file_tuple: Tuple[str, bytes, str],
        model: Optional[str] = None,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> str:
        """
        Transcribe audio recording using Groq Whisper model with centralized
        rate-limit handling, concurrency throttling, and retry backoff.
        Never logs audio content or transcripts.
        """
        client = self.get_client(max_retries=0)
        target_model = model or getattr(settings, "GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3")
        filename, audio_bytes, content_type = file_tuple

        logger.info(
            "Transcribing audio file: format=%s, size=%d bytes, model=%s",
            filename.split(".")[-1] if "." in filename else "unknown",
            len(audio_bytes),
            target_model,
        )

        async with self._semaphore:
            last_delay = 1.0
            for attempt in range(max_retries + 1):
                try:
                    kwargs: Dict[str, Any] = {
                        "file": (filename, audio_bytes, content_type),
                        "model": target_model,
                        "response_format": "json",
                        "timeout": timeout,
                    }
                    if language and language.strip():
                        kwargs["language"] = language.strip()
                    if prompt and prompt.strip():
                        kwargs["prompt"] = prompt.strip()

                    transcription = await client.audio.transcriptions.create(**kwargs)

                    text = getattr(transcription, "text", "") or ""
                    if isinstance(transcription, dict):
                        text = transcription.get("text", "")

                    return str(text).strip()

                except groq.RateLimitError as exc:
                    headers = dict(exc.response.headers) if hasattr(exc, "response") and exc.response else {}
                    logger.warning(
                        "Groq audio transcription rate limit encountered (attempt %d/%d): %s",
                        attempt + 1,
                        max_retries + 1,
                        exc.message if hasattr(exc, "message") else str(exc),
                    )

                    if is_daily_quota_exhausted(headers):
                        reset_time = headers.get("x-ratelimit-reset-requests", "unknown time")
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Daily Groq API quota exhausted. Resets in {reset_time}. Please try again later.",
                        ) from exc

                    if attempt < max_retries:
                        delay = parse_reset_delay(headers, default_delay=1.5 * (2 ** attempt))
                        jitter = random.uniform(0.1, 0.4)
                        total_sleep = min(delay + jitter, 5.0)
                        logger.info("Applying rate-limit backoff for audio: sleeping %.2fs", total_sleep)
                        await asyncio.sleep(total_sleep)
                        last_delay = total_sleep
                    else:
                        retry_sec = int(round(last_delay))
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=(
                                f"Rate limit exceeded: AI audio transcription is temporarily busy. "
                                f"Please wait {max(5, retry_sec)} seconds before retrying."
                            ),
                        ) from exc

                except groq.APITimeoutError as exc:
                    logger.warning("Groq audio transcription timed out on attempt %d", attempt + 1)
                    if attempt < max_retries:
                        await asyncio.sleep(1.0)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                            detail="Audio transcription request timed out. Please try again with a shorter recording.",
                        ) from exc

                except groq.APIConnectionError as exc:
                    logger.warning("Groq connection failed during transcription on attempt %d: %s", attempt + 1, type(exc).__name__)
                    if attempt < max_retries:
                        await asyncio.sleep(1.0)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Failed to connect to audio transcription service. Please check network connectivity.",
                        ) from exc

                except groq.APIStatusError as exc:
                    logger.error("Groq audio transcription status error: HTTP %s", exc.status_code)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Audio transcription service error (HTTP {exc.status_code}). Please try again.",
                    ) from exc


groq_manager = GroqClientManager()

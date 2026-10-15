import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
import groq
from fastapi import HTTPException

from app.core.groq_client import (
    GroqClientManager,
    parse_reset_delay,
    is_daily_quota_exhausted,
)


def make_rate_limit_error(headers: dict, message: str = "Rate limit reached") -> groq.RateLimitError:
    mock_response = httpx.Response(
        status_code=429,
        headers=headers,
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )
    return groq.RateLimitError(
        message=message,
        response=mock_response,
        body={"error": {"message": message, "code": "rate_limit_exceeded"}},
    )


def test_parse_reset_delay_retry_after():
    headers = {"retry-after": "2.5"}
    delay = parse_reset_delay(headers, default_delay=1.0)
    assert delay == 2.5


def test_parse_reset_delay_reset_tokens():
    headers = {"x-ratelimit-reset-tokens": "850ms"}
    delay = parse_reset_delay(headers, default_delay=1.0)
    assert delay == 0.85


def test_parse_reset_delay_reset_tokens_seconds():
    headers = {"x-ratelimit-reset-tokens": "3.2s"}
    delay = parse_reset_delay(headers, default_delay=1.0)
    assert delay == 3.2


def test_is_daily_quota_exhausted_detected():
    headers = {
        "x-ratelimit-remaining-requests": "0",
        "x-ratelimit-reset-requests": "14h22m",
    }
    assert is_daily_quota_exhausted(headers) is True


def test_is_daily_quota_exhausted_not_detected_when_tokens_only():
    headers = {
        "x-ratelimit-remaining-requests": "950",
        "x-ratelimit-remaining-tokens": "0",
        "x-ratelimit-reset-tokens": "1.2s",
    }
    assert is_daily_quota_exhausted(headers) is False


@pytest.mark.asyncio
async def test_execute_chat_completion_success():
    manager = GroqClientManager()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"result": "ok"}'
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch.object(manager, "get_client", return_value=mock_client):
        res = await manager.execute_chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            max_retries=1,
        )
        assert res == '{"result": "ok"}'
        assert mock_client.chat.completions.create.call_count == 1


@pytest.mark.asyncio
async def test_execute_chat_completion_retries_on_transient_429():
    manager = GroqClientManager()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"recovered": true}'
    mock_completion = MagicMock(choices=[mock_choice])

    err_429 = make_rate_limit_error({"x-ratelimit-reset-tokens": "100ms", "retry-after": "0.1"})

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[err_429, mock_completion])

    with patch.object(manager, "get_client", return_value=mock_client), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await manager.execute_chat_completion(
            messages=[{"role": "user", "content": "test transient"}],
            max_retries=1,
        )
        assert res == '{"recovered": true}'
        assert mock_client.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_execute_chat_completion_aborts_immediately_on_daily_quota():
    manager = GroqClientManager()
    daily_err = make_rate_limit_error({
        "x-ratelimit-remaining-requests": "0",
        "x-ratelimit-reset-requests": "8h15m",
    }, message="Daily limit reached")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=daily_err)

    with patch.object(manager, "get_client", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            await manager.execute_chat_completion(
                messages=[{"role": "user", "content": "test daily"}],
                max_retries=2,
            )
        assert exc_info.value.status_code == 429
        assert "Daily Groq API quota exhausted" in exc_info.value.detail
        # Should not retry repeatedly if daily quota is exhausted
        assert mock_client.chat.completions.create.call_count == 1


@pytest.mark.asyncio
async def test_execute_chat_completion_retry_exhaustion():
    manager = GroqClientManager()
    err_429 = make_rate_limit_error({"retry-after": "1.0"})

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[err_429, err_429])

    with patch.object(manager, "get_client", return_value=mock_client), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(HTTPException) as exc_info:
            await manager.execute_chat_completion(
                messages=[{"role": "user", "content": "test exhaustion"}],
                max_retries=1,
            )
        assert exc_info.value.status_code == 429
        assert "temporarily rate-limited" in exc_info.value.detail
        assert "Your response has not been lost" in exc_info.value.detail
        assert mock_client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_api_key_not_exposed_in_error_messages():
    manager = GroqClientManager()
    secret_key = "gsk_SUPER_SECRET_VALUE_12345"

    with patch("app.core.config.settings.GROQ_API_KEY", secret_key):
        err = make_rate_limit_error({"retry-after": "1.0"}, message="Rate limited")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=err)

        with patch.object(manager, "get_client", return_value=mock_client):
            try:
                await manager.execute_chat_completion(
                    messages=[{"role": "user", "content": "secret test"}],
                    max_retries=0,
                )
            except HTTPException as exc:
                assert secret_key not in exc.detail
                assert "gsk_" not in exc.detail

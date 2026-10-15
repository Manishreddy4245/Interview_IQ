import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
import groq
from fastapi import HTTPException

from app.core.groq_client import (
    GroqClientManager,
    sanitize_groq_error_message,
)
from app.schemas.interview import InterviewSetupRequest
from app.services.question_generator import (
    generate_initial_adaptive_question,
    generate_adaptive_questions,
)


def make_bad_request_error(body: dict, message: str = "Bad Request") -> groq.BadRequestError:
    mock_response = httpx.Response(
        status_code=400,
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )
    return groq.BadRequestError(
        message=message,
        response=mock_response,
        body=body,
    )


def test_sanitize_groq_error_message_extracts_clean_summary():
    # Simulates exact Groq token exhaustion error body observed in production
    body = {
        "error": {
            "message": "Failed to generate JSON. Please adjust your prompt. See 'failed_generation' for more details.",
            "type": "invalid_request_error",
            "code": "json_validate_failed",
            "failed_generation": "max completion tokens reached before generating a valid document",
        }
    }
    err = make_bad_request_error(body)
    sanitized = sanitize_groq_error_message(err)

    assert "Model output exceeded token limit before completing valid JSON" in sanitized
    assert "gsk_" not in sanitized


def test_sanitize_groq_error_message_redacts_api_keys_and_tokens():
    body = {
        "error": {
            "message": "Invalid auth header gsk_TESTSECRETKEY99887766 and Bearer eyJhbGciOiJIUzI1NiJ9.test",
            "type": "invalid_request_error",
            "code": "invalid_api_key",
        }
    }
    err = make_bad_request_error(body)
    sanitized = sanitize_groq_error_message(err)

    assert "gsk_TESTSECRETKEY99887766" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized
    assert "[REDACTED_TOKEN]" in sanitized


@pytest.mark.asyncio
async def test_execute_chat_completion_surfaces_sanitized_400_detail():
    manager = GroqClientManager()
    body = {
        "error": {
            "message": "Failed to generate JSON. Please adjust your prompt.",
            "type": "invalid_request_error",
            "code": "json_validate_failed",
            "failed_generation": "max completion tokens reached before generating a valid document",
        }
    }
    err_400 = make_bad_request_error(body)

    mock_client = MagicMock()
    # Fails repeatedly
    mock_client.chat.completions.create = AsyncMock(side_effect=err_400)

    with patch.object(manager, "get_client", return_value=mock_client), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(HTTPException) as exc_info:
            await manager.execute_chat_completion(
                messages=[{"role": "user", "content": "test"}],
                max_retries=1,
            )

        assert exc_info.value.status_code == 502
        assert "AI service error (HTTP 400):" in exc_info.value.detail
        assert "Model output exceeded token limit before completing valid JSON" in exc_info.value.detail
        # Asserts it is NOT the old generic uninformative message
        assert exc_info.value.detail != "AI service error (HTTP 400). Please try again."


@pytest.mark.asyncio
async def test_execute_chat_completion_recovers_from_token_truncation_via_retry():
    manager = GroqClientManager()
    body = {
        "error": {
            "message": "Failed to generate JSON.",
            "code": "json_validate_failed",
            "failed_generation": "max completion tokens reached before generating a valid document",
        }
    }
    err_400 = make_bad_request_error(body)

    mock_choice = MagicMock()
    mock_choice.message.content = '{"status": "recovered"}'
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    # First attempt fails with 400 token truncation, second attempt succeeds with bumped tokens
    mock_client.chat.completions.create = AsyncMock(side_effect=[err_400, mock_completion])

    with patch.object(manager, "get_client", return_value=mock_client), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await manager.execute_chat_completion(
            messages=[{"role": "user", "content": "generate"}],
            max_tokens=900,
            max_retries=1,
        )

        assert result == '{"status": "recovered"}'
        assert mock_client.chat.completions.create.call_count == 2
        # Verify the second call received increased max_tokens and reasoning_effort=low
        second_call_kwargs = mock_client.chat.completions.create.call_args_list[1][1]
        assert second_call_kwargs["max_tokens"] >= 1800
        assert second_call_kwargs["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_execute_chat_completion_drops_unsupported_reasoning_effort():
    manager = GroqClientManager()
    body = {
        "error": {
            "message": "`reasoning_effort` is not supported with this model",
            "type": "invalid_request_error",
        }
    }
    err_400 = make_bad_request_error(body)

    mock_choice = MagicMock()
    mock_choice.message.content = '{"model": "non_reasoning_ok"}'
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    # First call fails because model doesn't support reasoning_effort, second call succeeds without it
    mock_client.chat.completions.create = AsyncMock(side_effect=[err_400, mock_completion])

    with patch.object(manager, "get_client", return_value=mock_client):
        result = await manager.execute_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="allam-2-7b",
            reasoning_effort="low",
            max_retries=1,
        )

        assert result == '{"model": "non_reasoning_ok"}'
        assert mock_client.chat.completions.create.call_count == 2
        second_call_kwargs = mock_client.chat.completions.create.call_args_list[1][1]
        assert "reasoning_effort" not in second_call_kwargs


@pytest.mark.asyncio
async def test_question_generator_passes_sufficient_tokens_and_reasoning_effort():
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Algorithms, Data Structures",
        question_count=3,
        adaptive=True,
        interview_mode="CODING",
    )

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "id": "q_1",
        "question_number": 1,
        "title": "Two Sum Problem",
        "text": "Given array of ints, return indices...",
        "assessed_skill": "Algorithms",
        "difficulty": "Medium",
        "rubric": "Efficiency and correctness",
        "question_type": "coding",
        "function_name": "twoSum",
        "input_format": "nums: int[], target: int",
        "output_format": "int[]",
        "constraints": ["2 <= nums.length <= 10^4"],
        "examples": [{"example_number": 1, "input": "[2,7,11,15], 9", "output": "[0,1]"}],
        "test_cases": [{"id": "tc_1", "input": "[2,7,11,15], 9", "expected_output": "[0,1]", "is_hidden": False}],
    })
    mock_completion = MagicMock(choices=[mock_choice])

    with patch("app.core.groq_client.groq_manager.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        questions = await generate_initial_adaptive_question(setup)

        assert len(questions) == 1
        assert questions[0].question_type == "coding"
        assert mock_client.chat.completions.create.call_count == 1
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # Verify max_tokens is >= 2500 and reasoning_effort is low
        assert call_kwargs["max_tokens"] >= 2500
        assert call_kwargs["reasoning_effort"] == "low"
        assert call_kwargs["timeout"] >= 30.0

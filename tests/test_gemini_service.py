import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import httpx
from google import genai
from google.genai import errors
from google.genai import types

from app import gemini_service
from app.gemini_service import ExtractionError, GeminiService
from app.models import ReviewExtraction


@pytest.fixture
def service(monkeypatch):
    generate = AsyncMock()
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    monkeypatch.setattr(gemini_service.genai, "Client", lambda **kwargs: client)
    return GeminiService("test-placeholder", "gemini-2.5-flash"), generate


def test_schema_prompt_and_partial_fields_are_supported(service):
    instance, generate = service
    generate.return_value = SimpleNamespace(text=json.dumps({"original_language": "Korean", "translated_review": "I had nose surgery at ID Hospital.", "clinic_raw": "아이디병원", "procedure_raw": "코수술", "trust_signals": ["surgeon_named", "firsthand_experience", "firsthand_experience"]}))
    record = asyncio.run(instance.extract("아이디병원에서 코수술을 받았어요."))
    assert record.surgeon is None
    assert record.price is None
    assert "surgeon_named" not in record.trust_signals
    assert record.trust_signals.count("firsthand_experience") == 1
    assert "clinic_named" in record.trust_signals
    config = generate.call_args.kwargs["config"]
    assert config.response_schema is ReviewExtraction
    assert "untrusted data" in config.system_instruction
    assert "Never fabricate" in config.system_instruction


@pytest.mark.parametrize("text", ["", "{bad json", '{"original_language":"English"}', '{"original_language":"English","translated_review":" "}'])
def test_malformed_or_incomplete_model_output(service, text):
    instance, generate = service
    generate.return_value = SimpleNamespace(text=text)
    with pytest.raises(ExtractionError) as result:
        asyncio.run(instance.extract("A review."))
    assert result.value.status_code == 502


def test_invented_raw_clinic_is_rejected(service):
    instance, generate = service
    generate.return_value = SimpleNamespace(text=json.dumps({"original_language": "English", "translated_review": "I had surgery.", "clinic_raw": "ID Hospital"}))
    with pytest.raises(ExtractionError) as result:
        asyncio.run(instance.extract("I had surgery."))
    assert result.value.status_code == 502


@pytest.mark.parametrize("upstream,expected", [(429, 429), (403, 503), (404, 503), (500, 502)])
def test_provider_errors_never_expose_upstream_secrets(service, upstream, expected):
    instance, generate = service
    generate.side_effect = errors.APIError(upstream, {"error": {"message": "sensitive-credential-and-review"}})
    with pytest.raises(ExtractionError) as result:
        asyncio.run(instance.extract("A private review."))
    assert result.value.status_code == expected
    assert "sensitive-credential-and-review" not in result.value.message
    assert "private review" not in result.value.message


def test_timeout_is_bounded_and_retryable(service):
    instance, generate = service
    generate.side_effect = asyncio.TimeoutError()
    with pytest.raises(ExtractionError) as result:
        asyncio.run(instance.extract("A review."))
    assert result.value.status_code == 504


def test_real_sdk_serializes_pydantic_schema_without_network(monkeypatch):
    """Exercise the actual SDK conversion/parse path with an in-memory HTTP transport."""
    requests = []
    source_record = {"original_language": "English", "translated_review": "I had rhinoplasty at ID Plastic Surgery.",
                     "clinic_raw": "ID Plastic Surgery", "procedure_raw": "rhinoplasty"}

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            "candidates": [{"content": {"role": "model", "parts": [{"text": json.dumps(source_record)}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20, "totalTokenCount": 30},
        })

    sdk_client = genai.Client(api_key="test-placeholder", http_options=types.HttpOptions(
        async_client_args={"transport": httpx.MockTransport(respond)}))
    monkeypatch.setattr(gemini_service.genai, "Client", lambda **kwargs: sdk_client)

    async def run():
        instance = GeminiService("test-placeholder", "gemini-2.5-flash")
        try:
            return await instance.extract("I had rhinoplasty at ID Plastic Surgery.")
        finally:
            await instance.close()

    record = asyncio.run(run())
    assert record.clinic_raw == "ID Plastic Surgery"
    assert record.surgeon is None
    assert len(requests) == 1
    config = requests[0]["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert "clinic_raw" in config["responseSchema"]["properties"]
    assert "systemInstruction" in requests[0]

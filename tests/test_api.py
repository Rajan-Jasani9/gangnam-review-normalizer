from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.gemini_service import ExtractionError
from app.models import ReviewExtraction
from main import app


@pytest.fixture
def client(monkeypatch):
    # No external calls and no dependence on a developer's real API credentials.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(app) as client:
        yield client


def test_pages_docs_and_health_load(client):
    assert client.get("/").status_code == 200
    assert "Review Normalizer" in client.get("/").text
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["paths"]["/api/normalize"]
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]


@pytest.mark.parametrize("payload", [{}, {"review": ""}, {"review": " \n "}, {"review": None}, {"review": 123}, {"review": "a" * 10001}, {"review": "hello", "extra": "value"}])
def test_bad_requests_are_validated_before_calling_provider(client, payload):
    app.state.gemini.extract = AsyncMock(side_effect=AssertionError("Must not call Gemini"))
    response = client.post("/api/normalize", json=payload)
    assert response.status_code == 422
    app.state.gemini.extract.assert_not_awaited()


def test_invalid_json_is_helpful(client):
    response = client.post("/api/normalize", content="{broken}", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "non-empty" in response.json()["detail"]


def test_missing_key_is_an_explicit_configuration_error(client):
    response = client.post("/api/normalize", json={"review": "I had nose surgery."})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("raw", ["아이디병원", "ID Plastic Surgery"])
def test_full_api_flow_resolves_both_demo_aliases(client, raw):
    extracted = ReviewExtraction(original_language="Korean" if raw == "아이디병원" else "English", translated_review="I had nose surgery and experienced swelling.", clinic_raw=raw, procedure_raw="코수술", procedure_normalized="Nose surgery", negative_outcomes=["Swelling"])
    app.state.gemini.extract = AsyncMock(return_value=extracted)
    response = client.post("/api/normalize", json={"review": f"{raw}에서 코수술을 받았어요."})
    assert response.status_code == 200
    data = response.json()
    assert data["normalization"]["clinic_canonical"] == "ID Hospital"
    assert data["extraction"]["procedure_normalized"] == "Rhinoplasty"
    assert data["extraction"]["surgeon"] is None
    assert data["extraction"]["price"] is None


def test_api_preserves_unknown_clinic(client):
    app.state.gemini.extract = AsyncMock(return_value=ReviewExtraction(original_language="English", translated_review="I visited Sunshine Aesthetic Center.", clinic_raw="Sunshine Aesthetic Center"))
    result = client.post("/api/normalize", json={"review": "I visited Sunshine Aesthetic Center."}).json()
    assert result["normalization"]["status"] == "unresolved"
    assert result["normalization"]["clinic_canonical"] == "Sunshine Aesthetic Center"


@pytest.mark.parametrize("code", [429, 502, 503, 504])
def test_upstream_errors_have_useful_http_statuses(client, code):
    app.state.gemini.extract = AsyncMock(side_effect=ExtractionError(code, "Please try again."))
    response = client.post("/api/normalize", json={"review": "A review."})
    assert response.status_code == code
    assert response.json() == {"detail": "Please try again."}

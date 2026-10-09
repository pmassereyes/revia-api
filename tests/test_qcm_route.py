import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers.qcm import get_provider
from app.schemas import QCMResponse
from app import ratelimit

FIXTURE = Path(__file__).parent / "fixtures" / "reponse_exemple.json"
PDF = b"%PDF-1.4 faux pdf pour les tests"
HEADERS = {"X-API-Token": "test-token"}


class FakeProvider:
    async def generate_qcm(self, pdf: bytes, nb_questions: int) -> QCMResponse:
        return QCMResponse.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.fixture
def client(monkeypatch):
    from app import ratelimit

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "test-token")
    ratelimit.reset()
    app.dependency_overrides[get_provider] = lambda: FakeProvider()
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    assert post(client).status_code == 200
    assert post(client).status_code == 200
    r = post(client)
    assert r.status_code == 429
    assert r.json()["code"] == "rate_limited"


def post(client, headers=HEADERS, content=PDF):
    return client.post(
        "/v1/qcm",
        headers=headers,
        files={"file": ("cours.pdf", content, "application/pdf")},
        data={"nb_questions": "5"},
    )


def test_ok(client):
    r = post(client)
    assert r.status_code == 200
    assert r.json()["qcm"][0]["indexBonneReponse"] == 1


def test_sans_jeton(client):
    r = post(client, headers={})
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_token"


def test_pdf_trop_lourd(client, monkeypatch):
    monkeypatch.setattr(settings, "max_pdf_mb", 0)
    r = post(client)
    assert r.status_code == 413


def test_pas_un_pdf(client):
    r = post(client, content=b"ceci n'est pas un pdf")
    assert r.status_code == 400
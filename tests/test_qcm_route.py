# test_qcm_route.py - RevIA API
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.cache import CachedProvider
from app.config import settings
from app.main import app
from app.routers.qcm import get_provider
from app.schemas import QCMResponse

FIXTURE = Path(__file__).parent / "fixtures" / "reponse_exemple.json"
PDF = b"%PDF-1.4 faux pdf pour les tests"
HEADERS = {"X-API-Token": "test-token"}


class FakeProvider:
    async def generate_qcm(self, pdf: bytes, nb_questions: int) -> QCMResponse:
        return QCMResponse.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


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

def test_nb_questions_hors_bornes(client):
    r = client.post(
        "/v1/qcm",
        headers=HEADERS,
        files={"file": ("cours.pdf", PDF, "application/pdf")},
        data={"nb_questions": "31"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_request"
    assert "nb_questions" in r.json()["message"]


def test_fichier_manquant(client):
    r = client.post("/v1/qcm", headers=HEADERS, data={"nb_questions": "5"})
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_request"
    assert "file" in r.json()["message"]


def test_cle_gemini_absente(client, monkeypatch):
    app.dependency_overrides.clear()  # on teste le vrai get_provider
    get_provider.cache_clear()
    monkeypatch.setattr(settings, "gemini_api_key", "")
    r = post(client)
    assert r.status_code == 503
    assert r.json()["code"] == "provider_unavailable"


class ProviderEnPanne:
    async def generate_qcm(self, pdf: bytes, nb_questions: int) -> QCMResponse:
        raise RuntimeError("panne imprévue")


def test_erreur_imprevue(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "test-token")
    ratelimit.reset()
    app.dependency_overrides[get_provider] = lambda: ProviderEnPanne()
    try:
        r = post(TestClient(app, raise_server_exceptions=False))
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 500
    assert r.json() == {"code": "internal_error", "message": "Erreur interne du serveur."}


def test_provider_construit_avec_cle(monkeypatch, tmp_path):
    get_provider.cache_clear()
    monkeypatch.setattr(settings, "gemini_api_key", "cle-factice")
    monkeypatch.setattr(settings, "cache_dir", str(tmp_path))
    try:
        assert isinstance(get_provider(), CachedProvider)
    finally:
        get_provider.cache_clear()

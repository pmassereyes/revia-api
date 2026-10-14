# test_gemini_provider.py - RevIA API
import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.config import settings
from app.errors import GenerationFailedError, QuotaExceededError
from app.prompts.qcm import build_prompt
from app.providers.gemini import GeminiProvider
from app.schemas import QCMResponse

FIXTURE = Path(__file__).parent / "fixtures" / "reponse_exemple.json"
PDF = b"%PDF-1.4 contenu du cours"


class FakeModels:
    """Remplace client.aio.models : renvoie une réponse ou lève une erreur, et garde les appels."""

    def __init__(self, texte: str | None = None, erreur: Exception | None = None) -> None:
        self.texte = texte
        self.erreur = erreur
        self.appels: list[dict] = []

    async def generate_content(self, **kwargs):
        self.appels.append(kwargs)
        if self.erreur:
            raise self.erreur
        return SimpleNamespace(text=self.texte)


def provider_avec(models: FakeModels, monkeypatch) -> GeminiProvider:
    monkeypatch.setattr(settings, "gemini_api_key", "cle-factice")
    provider = GeminiProvider()
    provider._client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return provider


def erreur_gemini(code: int) -> errors.APIError:
    classe = errors.ClientError if code < 500 else errors.ServerError
    return classe(code, {"error": {"code": code, "message": "erreur simulée", "status": "X"}})


def test_reponse_valide(monkeypatch):
    models = FakeModels(texte=FIXTURE.read_text(encoding="utf-8"))
    rep = asyncio.run(provider_avec(models, monkeypatch).generate_qcm(PDF, 5))

    assert isinstance(rep, QCMResponse)
    assert rep.qcm[0].index_bonne_reponse == 1
    appel = models.appels[0]
    assert appel["model"] == settings.gemini_model
    pdf_envoye, prompt = appel["contents"]
    assert pdf_envoye.inline_data.mime_type == "application/pdf"
    assert pdf_envoye.inline_data.data == PDF
    assert prompt == build_prompt(5)
    assert appel["config"].response_mime_type == "application/json"
    assert appel["config"].response_schema is QCMResponse


def test_quota_gemini_depasse(monkeypatch):
    provider = provider_avec(FakeModels(erreur=erreur_gemini(429)), monkeypatch)
    with pytest.raises(QuotaExceededError):
        asyncio.run(provider.generate_qcm(PDF, 5))


@pytest.mark.parametrize("code", [400, 403, 500, 503])
def test_autre_erreur_gemini(monkeypatch, code):
    provider = provider_avec(FakeModels(erreur=erreur_gemini(code)), monkeypatch)
    with pytest.raises(GenerationFailedError):
        asyncio.run(provider.generate_qcm(PDF, 5))


def qcm_index_hors_bornes() -> str:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["qcm"][0]["indexBonneReponse"] = 9
    return json.dumps(data)


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("ceci n'est pas du json", id="pas-du-json"),
        pytest.param('{"qcm": []}', id="qcm-vide"),
        pytest.param(qcm_index_hors_bornes(), id="index-hors-bornes"),
        pytest.param(None, id="reponse-vide"),
    ],
)
def test_reponse_inexploitable(monkeypatch, texte):
    provider = provider_avec(FakeModels(texte=texte), monkeypatch)
    with pytest.raises(GenerationFailedError):
        asyncio.run(provider.generate_qcm(PDF, 5))


def test_echec_gemini_journalise_sans_cle(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="app")
    provider = provider_avec(FakeModels(erreur=erreur_gemini(503)), monkeypatch)
    with pytest.raises(GenerationFailedError):
        asyncio.run(provider.generate_qcm(PDF, 5))
    assert f"echec_gemini code=503 statut=X modele={settings.gemini_model}" in caplog.text
    assert "message=erreur simulée" in caplog.text
    assert "cle-factice" not in caplog.text


def test_reponse_invalide_journalisee(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="app")
    provider = provider_avec(FakeModels(texte='{"qcm": []}'), monkeypatch)
    with pytest.raises(GenerationFailedError):
        asyncio.run(provider.generate_qcm(PDF, 5))
    assert caplog.messages == ["reponse_gemini_invalide erreurs=1 premier_champ=qcm type=too_short"]

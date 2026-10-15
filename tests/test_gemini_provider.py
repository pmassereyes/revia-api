# test_gemini_provider.py - RevIA API
import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

from app.config import settings
from app.errors import (
    GenerationFailedError,
    GenerationTimeoutError,
    ProviderOverloadedError,
    QuotaExceededError,
)
from app.prompts.qcm import build_prompt
from app.providers import gemini
from app.providers.gemini import GeminiProvider
from app.schemas import QCMResponse

FIXTURE = Path(__file__).parent / "fixtures" / "reponse_exemple.json"
PDF = b"%PDF-1.4 contenu du cours"


class FakeModels:
    """Remplace client.aio.models et garde les appels. Chaque appel renvoie l'issue suivante
    de la suite (texte de réponse ou exception à lever) ; la dernière issue se répète."""

    def __init__(
        self,
        texte: str | None = None,
        erreur: Exception | None = None,
        suite: list[str | Exception] | None = None,
    ) -> None:
        self.suite = suite or [erreur or texte]
        self.appels: list[dict] = []

    async def generate_content(self, **kwargs):
        self.appels.append(kwargs)
        issue = self.suite[min(len(self.appels), len(self.suite)) - 1]
        if isinstance(issue, Exception):
            raise issue
        return SimpleNamespace(text=issue)


def provider_avec(models: FakeModels, monkeypatch) -> GeminiProvider:
    monkeypatch.setattr(settings, "gemini_api_key", "cle-factice")
    monkeypatch.setattr(settings, "gemini_model", "modele-principal")
    monkeypatch.setattr(settings, "gemini_fallback_model", "modele-secours")
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
    appel = provider.generate_qcm(PDF, 5)  # la coroutine est créée hors du bloc raises
    with pytest.raises(QuotaExceededError):
        asyncio.run(appel)


@pytest.mark.parametrize("code", [400, 403, 500])
def test_autre_erreur_gemini(monkeypatch, code):
    provider = provider_avec(FakeModels(erreur=erreur_gemini(code)), monkeypatch)
    appel = provider.generate_qcm(PDF, 5)  # la coroutine est créée hors du bloc raises
    with pytest.raises(GenerationFailedError):
        asyncio.run(appel)


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
    appel = provider.generate_qcm(PDF, 5)  # la coroutine est créée hors du bloc raises
    with pytest.raises(GenerationFailedError):
        asyncio.run(appel)


def test_echec_gemini_journalise_sans_cle(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="app")
    provider = provider_avec(FakeModels(erreur=erreur_gemini(500)), monkeypatch)
    appel = provider.generate_qcm(PDF, 5)  # la coroutine est créée hors du bloc raises
    with pytest.raises(GenerationFailedError):
        asyncio.run(appel)
    assert "echec_gemini code=500 statut=X modele=modele-principal" in caplog.text
    assert "message=erreur simulée" in caplog.text
    assert "cle-factice" not in caplog.text


def test_reponse_invalide_journalisee(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="app")
    provider = provider_avec(FakeModels(texte='{"qcm": []}'), monkeypatch)
    appel = provider.generate_qcm(PDF, 5)  # la coroutine est créée hors du bloc raises
    with pytest.raises(GenerationFailedError):
        asyncio.run(appel)
    assert caplog.messages == ["reponse_gemini_invalide erreurs=1 premier_champ=qcm type=too_short"]


def test_client_configure_avec_delai_et_tentatives(monkeypatch):
    recus = {}
    monkeypatch.setattr(gemini.genai, "Client", lambda **kwargs: recus.update(kwargs))
    monkeypatch.setattr(settings, "gemini_timeout_s", 90)
    monkeypatch.setattr(settings, "gemini_attempts", 3)
    GeminiProvider()
    options = recus["http_options"]
    assert options.timeout == 90_000
    assert options.retry_options.attempts == 3
    assert options.retry_options.initial_delay == 2.0
    assert 503 in options.retry_options.http_status_codes
    assert 429 not in options.retry_options.http_status_codes


def test_delai_depasse(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="app")
    provider = provider_avec(FakeModels(erreur=httpx.ReadTimeout("trop lent")), monkeypatch)
    appel = provider.generate_qcm(PDF, 5)
    with pytest.raises(GenerationTimeoutError):
        asyncio.run(appel)
    attendu = (
        f"delai_gemini_depasse modele=modele-principal timeout_s={settings.gemini_timeout_s} "
        f"tentatives={settings.gemini_attempts}"
    )
    assert caplog.messages == [attendu]


def test_erreur_reseau(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="app")
    provider = provider_avec(FakeModels(erreur=httpx.ConnectError("injoignable")), monkeypatch)
    appel = provider.generate_qcm(PDF, 5)
    with pytest.raises(GenerationFailedError):
        asyncio.run(appel)
    assert caplog.messages == ["echec_reseau_gemini modele=modele-principal exception=ConnectError"]


def test_appel_reussi_journalise(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="app")
    provider = provider_avec(FakeModels(texte=FIXTURE.read_text(encoding="utf-8")), monkeypatch)
    asyncio.run(provider.generate_qcm(PDF, 5))
    assert len(caplog.messages) == 1
    assert caplog.messages[0].startswith("appel_gemini modele=modele-principal duree_ms=")


@pytest.mark.parametrize("code", [503, 429])
def test_bascule_sur_le_modele_de_secours(monkeypatch, caplog, code):
    caplog.set_level(logging.WARNING, logger="app")
    models = FakeModels(suite=[erreur_gemini(code), FIXTURE.read_text(encoding="utf-8")])
    rep = asyncio.run(provider_avec(models, monkeypatch).generate_qcm(PDF, 5))
    assert isinstance(rep, QCMResponse)
    assert [a["model"] for a in models.appels] == ["modele-principal", "modele-secours"]
    assert "bascule_modele_secours de=modele-principal vers=modele-secours" in caplog.messages


def test_surcharge_sans_modele_de_secours(monkeypatch):
    models = FakeModels(erreur=erreur_gemini(503))
    provider = provider_avec(models, monkeypatch)
    monkeypatch.setattr(settings, "gemini_fallback_model", "")
    appel = provider.generate_qcm(PDF, 5)
    with pytest.raises(ProviderOverloadedError):
        asyncio.run(appel)
    assert len(models.appels) == 1


def test_secours_identique_au_principal_ignore(monkeypatch):
    models = FakeModels(erreur=erreur_gemini(503))
    provider = provider_avec(models, monkeypatch)
    monkeypatch.setattr(settings, "gemini_fallback_model", "modele-principal")
    appel = provider.generate_qcm(PDF, 5)
    with pytest.raises(ProviderOverloadedError):
        asyncio.run(appel)
    assert len(models.appels) == 1


def test_secours_aussi_surcharge(monkeypatch):
    models = FakeModels(erreur=erreur_gemini(503))
    appel = provider_avec(models, monkeypatch).generate_qcm(PDF, 5)
    with pytest.raises(ProviderOverloadedError):
        asyncio.run(appel)
    assert [a["model"] for a in models.appels] == ["modele-principal", "modele-secours"]


@pytest.mark.parametrize(
    "erreur",
    [pytest.param(erreur_gemini(504), id="504-gemini"), pytest.param(httpx.ReadTimeout("lent"), id="delai")],
)
def test_pas_de_bascule_sur_delai_depasse(monkeypatch, erreur):
    models = FakeModels(erreur=erreur)
    appel = provider_avec(models, monkeypatch).generate_qcm(PDF, 5)
    with pytest.raises(GenerationTimeoutError):
        asyncio.run(appel)
    assert len(models.appels) == 1

# gemini.py - RevIA API
import logging
import time

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.config import settings
from app.errors import (
    ApiError,
    GenerationFailedError,
    GenerationTimeoutError,
    ProviderOverloadedError,
    QuotaExceededError,
)
from app.prompts.qcm import build_prompt
from app.schemas import QCMResponse

logger = logging.getLogger(__name__)

# Erreurs passagères côté Gemini. Pas de 429 : un quota épuisé ne revient pas en quelques secondes.
# google-genai retente aussi, de lui-même, les dépassements de délai et les erreurs de connexion.
CODES_A_RETENTER = [500, 502, 503, 504]
PAUSE_AVANT_NOUVEL_ESSAI_S = 2.0  # les pics de surcharge observés durent plus d'une seconde


class GeminiProvider:
    def __init__(self) -> None:
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=settings.gemini_timeout_s * 1000,  # en millisecondes
                retry_options=types.HttpRetryOptions(
                    attempts=settings.gemini_attempts,
                    initial_delay=PAUSE_AVANT_NOUVEL_ESSAI_S,
                    http_status_codes=CODES_A_RETENTER,
                ),
            ),
        )

    async def generate_qcm(self, pdf: bytes, nb_questions: int) -> QCMResponse:
        try:
            return await self._generer(settings.gemini_model, pdf, nb_questions)
        except (ProviderOverloadedError, QuotaExceededError):
            # Surcharge et quota sont propres à un modèle : le modèle de secours peut répondre.
            # Pas de bascule sur un délai dépassé, qui doublerait une attente déjà longue.
            secours = settings.gemini_fallback_model
            if not secours or secours == settings.gemini_model:
                raise
            logger.warning("bascule_modele_secours de=%s vers=%s", settings.gemini_model, secours)
            return await self._generer(secours, pdf, nb_questions)

    async def _generer(self, modele: str, pdf: bytes, nb_questions: int) -> QCMResponse:
        debut = time.perf_counter()
        try:
            response = await self._client.aio.models.generate_content(
                model=modele,
                contents=[
                    types.Part.from_bytes(data=pdf, mime_type="application/pdf"),
                    build_prompt(nb_questions),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=QCMResponse,
                ),
            )
        except errors.APIError as e:
            logger.warning(
                "echec_gemini code=%s statut=%s modele=%s message=%s",
                e.code, e.status, modele, e.message,
            )
            raise erreur_api(e) from e
        except httpx.TimeoutException as e:
            logger.warning(
                "delai_gemini_depasse modele=%s timeout_s=%d tentatives=%d",
                modele, settings.gemini_timeout_s, settings.gemini_attempts,
            )
            raise GenerationTimeoutError("Gemini n'a pas répondu à temps, réessaie.") from e
        except httpx.TransportError as e:
            logger.warning("echec_reseau_gemini modele=%s exception=%s", modele, type(e).__name__)
            raise GenerationFailedError("Échec de l'appel à Gemini.") from e
        logger.info("appel_gemini modele=%s duree_ms=%d", modele, (time.perf_counter() - debut) * 1000)

        try:
            return QCMResponse.model_validate_json(response.text)
        except ValidationError as e:  # couvre aussi le JSON invalide et un texte à None
            premiere = e.errors()[0]
            logger.warning(
                "reponse_gemini_invalide erreurs=%d premier_champ=%s type=%s",
                e.error_count(), ".".join(map(str, premiere["loc"])) or "-", premiere["type"],
            )
            raise GenerationFailedError("Réponse de Gemini invalide.") from e


def erreur_api(e: errors.APIError) -> ApiError:
    """Traduit une erreur de l'API Gemini, nouvelles tentatives épuisées, en erreur de l'API RevIA."""
    if e.code == 429:
        return QuotaExceededError("Quota Gemini dépassé, réessaie plus tard.")
    if e.code == 503:
        return ProviderOverloadedError("Gemini est surchargé, réessaie dans quelques minutes.")
    if e.code == 504:
        return GenerationTimeoutError("Gemini n'a pas répondu à temps, réessaie.")
    return GenerationFailedError("Échec de l'appel à Gemini.")

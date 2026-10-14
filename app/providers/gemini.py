# gemini.py - RevIA API
import logging

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.config import settings
from app.errors import GenerationFailedError, GenerationTimeoutError, QuotaExceededError
from app.prompts.qcm import build_prompt
from app.schemas import QCMResponse

logger = logging.getLogger(__name__)

# Erreurs passagères côté Gemini. Pas de 429 : un quota épuisé ne revient pas en quelques secondes.
# google-genai retente aussi, de lui-même, les dépassements de délai et les erreurs de connexion.
CODES_A_RETENTER = [500, 502, 503, 504]


class GeminiProvider:
    def __init__(self) -> None:
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=settings.gemini_timeout_s * 1000,  # en millisecondes
                retry_options=types.HttpRetryOptions(
                    attempts=settings.gemini_attempts,
                    http_status_codes=CODES_A_RETENTER,
                ),
            ),
        )

    async def generate_qcm(self, pdf: bytes, nb_questions: int) -> QCMResponse:
        try:
            response = await self._client.aio.models.generate_content(
                model=settings.gemini_model,
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
                e.code, e.status, settings.gemini_model, e.message,
            )
            if e.code == 429:
                raise QuotaExceededError("Quota Gemini dépassé, réessaie plus tard.") from e
            raise GenerationFailedError("Échec de l'appel à Gemini.") from e
        except httpx.TimeoutException as e:
            logger.warning(
                "delai_gemini_depasse timeout_s=%d tentatives=%d",
                settings.gemini_timeout_s, settings.gemini_attempts,
            )
            raise GenerationTimeoutError("Gemini n'a pas répondu à temps, réessaie.") from e
        except httpx.TransportError as e:
            logger.warning("echec_reseau_gemini exception=%s", type(e).__name__)
            raise GenerationFailedError("Échec de l'appel à Gemini.") from e

        try:
            return QCMResponse.model_validate_json(response.text)
        except ValidationError as e:  # couvre aussi le JSON invalide et un texte à None
            premiere = e.errors()[0]
            logger.warning(
                "reponse_gemini_invalide erreurs=%d premier_champ=%s type=%s",
                e.error_count(), ".".join(map(str, premiere["loc"])) or "-", premiere["type"],
            )
            raise GenerationFailedError("Réponse de Gemini invalide.") from e
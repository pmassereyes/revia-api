# gemini.py - RevIA API
import logging

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.config import settings
from app.errors import GenerationFailedError, QuotaExceededError
from app.prompts.qcm import build_prompt
from app.schemas import QCMResponse

logger = logging.getLogger(__name__)


class GeminiProvider:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)

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

        try:
            return QCMResponse.model_validate_json(response.text)
        except ValidationError as e:  # couvre aussi le JSON invalide et un texte à None
            premiere = e.errors()[0]
            logger.warning(
                "reponse_gemini_invalide erreurs=%d premier_champ=%s type=%s",
                e.error_count(), ".".join(map(str, premiere["loc"])) or "-", premiere["type"],
            )
            raise GenerationFailedError("Réponse de Gemini invalide.") from e
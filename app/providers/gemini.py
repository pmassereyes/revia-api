# gemini.py - RevIA API
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.config import settings
from app.errors import GenerationFailedError, QuotaExceededError
from app.prompts.qcm import build_prompt
from app.schemas import QCMResponse


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
            if e.code == 429:
                raise QuotaExceededError("Quota Gemini dépassé, réessaie plus tard.") from e
            raise GenerationFailedError("Échec de l'appel à Gemini.") from e

        try:
            return QCMResponse.model_validate_json(response.text)
        except (ValidationError, ValueError, TypeError) as e:
            raise GenerationFailedError("Réponse de Gemini invalide.") from e
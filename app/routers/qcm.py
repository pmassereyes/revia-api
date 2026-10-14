# qcm.py - RevIA API
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.auth import verify_token
from app.cache import CachedProvider
from app.config import settings
from app.errors import InvalidPdfError, PdfTooLargeError
from app.providers.base import QCMProvider
from app.providers.gemini import GeminiProvider
from app.ratelimit import rate_limit
from app.schemas import QCMResponse

router = APIRouter(prefix="/v1", tags=["qcm"])


@lru_cache
def get_provider() -> QCMProvider:
    return CachedProvider(GeminiProvider(), settings.cache_dir)


@router.post(
    "/qcm",
    response_model=QCMResponse,
    dependencies=[Depends(verify_token), Depends(rate_limit)],
)
async def create_qcm(
    file: Annotated[UploadFile, File()],
    provider: Annotated[QCMProvider, Depends(get_provider)],
    nb_questions: Annotated[int, Form(ge=1, le=30)] = 10,
) -> QCMResponse:
    max_bytes = settings.max_pdf_mb * 1024 * 1024
    pdf = await file.read(max_bytes + 1)  # on ne lit jamais plus que la limite + 1 octet
    if len(pdf) > max_bytes:
        raise PdfTooLargeError(f"PDF trop lourd (max {settings.max_pdf_mb} Mo).")
    if not pdf.startswith(b"%PDF-"):
        raise InvalidPdfError("Le fichier n'est pas un PDF valide.")
    return await provider.generate_qcm(pdf, nb_questions)
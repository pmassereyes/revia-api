# qcm.py - RevIA API
import logging
import time
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile

from app.auth import verify_token
from app.cache import CachedProvider
from app.config import settings
from app.errors import InvalidPdfError, PdfTooLargeError, ProviderUnavailableError
from app.logs import empreinte
from app.melange import melanger_propositions
from app.providers.base import QCMProvider
from app.providers.gemini import GeminiProvider
from app.ratelimit import rate_limit
from app.schemas import QCMResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["qcm"])


@lru_cache
def get_provider() -> QCMProvider:
    # Une exception n'est pas mise en cache par lru_cache : la clé est revérifiée à chaque requête
    if not settings.gemini_api_key:
        raise ProviderUnavailableError("Le service de génération n'est pas configuré.")
    return CachedProvider(GeminiProvider(), settings.cache_dir)


@router.post(
    "/qcm",
    response_model=QCMResponse,
    dependencies=[Depends(verify_token)],
)
async def create_qcm(
    file: Annotated[UploadFile, File()],
    provider: Annotated[QCMProvider, Depends(get_provider)],
    x_api_token: Annotated[str, Header()] = "",
    nb_questions: Annotated[int, Form(ge=1, le=30)] = 10,
) -> QCMResponse:
    # Décompté ici et non en dépendance : FastAPI exécute toutes les dépendances avant de
    # signaler les erreurs de validation, et une requête rejetée en 422 consommerait le quota
    rate_limit(x_api_token)
    max_bytes = settings.max_pdf_mb * 1024 * 1024
    pdf = await file.read(max_bytes + 1)  # on ne lit jamais plus que la limite + 1 octet
    if len(pdf) > max_bytes:
        raise PdfTooLargeError(f"PDF trop lourd (max {settings.max_pdf_mb} Mo).")
    if not pdf.startswith(b"%PDF-"):
        raise InvalidPdfError("Le fichier n'est pas un PDF valide.")
    debut = time.perf_counter()
    # Mélange appliqué ici, après le cache : il couvre aussi les QCM générés avant son ajout
    resultat = melanger_propositions(await provider.generate_qcm(pdf, nb_questions))
    logger.info(
        "generation empreinte=%s pdf_ko=%d nb_demande=%d nb_obtenu=%d avertissement=%s duree_ms=%d",
        empreinte(pdf),
        len(pdf) // 1024,
        nb_questions,
        len(resultat.qcm),
        "oui" if resultat.avertissement else "non",
        (time.perf_counter() - debut) * 1000,
    )
    return resultat
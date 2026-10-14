# cache.py - RevIA API
import hashlib
import logging
import os
from pathlib import Path

from app.config import settings
from app.logs import empreinte
from app.prompts.qcm import PROMPT_VERSION
from app.providers.base import QCMProvider
from app.schemas import QCMResponse

logger = logging.getLogger(__name__)


class CachedProvider:
    def __init__(self, inner: QCMProvider, cache_dir: str | Path) -> None:
        self._inner = inner
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(pdf: bytes, nb_questions: int) -> str:
        pdf_hash = hashlib.sha256(pdf).hexdigest()
        raw = f"{pdf_hash}|{nb_questions}|{settings.gemini_model}|{PROMPT_VERSION}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def generate_qcm(self, pdf: bytes, nb_questions: int) -> QCMResponse:
        path = self._dir / f"{self._key(pdf, nb_questions)}.json"

        if path.exists():
            try:
                cached = QCMResponse.model_validate_json(path.read_text(encoding="utf-8"))
                logger.info("cache=hit empreinte=%s", empreinte(pdf))
                return cached
            except ValueError:
                logger.warning("cache=corrompu empreinte=%s", empreinte(pdf))
                path.unlink(missing_ok=True)  # fichier corrompu : on régénère

        logger.info("cache=miss empreinte=%s", empreinte(pdf))
        result = await self._inner.generate_qcm(pdf, nb_questions)

        tmp = path.with_suffix(".tmp")
        tmp.write_text(result.model_dump_json(by_alias=True), encoding="utf-8")
        os.replace(tmp, path)  # écriture atomique
        return result
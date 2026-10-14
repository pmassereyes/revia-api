# logs.py - RevIA API
import hashlib
import logging

from app.config import settings

FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging() -> None:
    """Journaux des modules « app.* », en plus de ceux d'uvicorn. Appel répétable sans doublon."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT))
    logger = logging.getLogger("app")
    logger.handlers = [handler]
    logger.setLevel(settings.log_level.upper())


def empreinte(pdf: bytes) -> str:
    """Identifie un PDF dans les journaux sans en révéler le contenu."""
    return hashlib.sha256(pdf).hexdigest()[:8]

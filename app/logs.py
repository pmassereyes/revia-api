# logs.py - RevIA API
import hashlib
import logging

from app.config import settings

FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging() -> None:
    """Journaux de l'application et des nouvelles tentatives Gemini. Appel répétable sans doublon."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT))
    # google_genai._api_client annonce ses nouvelles tentatives vers Gemini (niveau INFO)
    for nom in ("app", "google_genai._api_client"):
        logger = logging.getLogger(nom)
        logger.handlers = [handler]
        logger.setLevel(settings.log_level.upper())


def empreinte(pdf: bytes) -> str:
    """Identifie un PDF dans les journaux sans en révéler le contenu."""
    return hashlib.sha256(pdf).hexdigest()[:8]

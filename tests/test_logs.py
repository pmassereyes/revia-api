# test_logs.py - RevIA API
import hashlib
import logging

from app.config import settings
from app.logs import empreinte, setup_logging


def test_niveau_regle_par_la_config_sans_doublon(monkeypatch):
    logger = logging.getLogger("app")
    niveau_initial = logger.level
    monkeypatch.setattr(settings, "log_level", "debug")
    try:
        setup_logging()
        setup_logging()
        for nom in ("app", "google_genai._api_client"):
            assert logging.getLogger(nom).level == logging.DEBUG
            assert len(logging.getLogger(nom).handlers) == 1
    finally:
        logger.setLevel(niveau_initial)
        logging.getLogger("google_genai._api_client").setLevel(niveau_initial)


def test_empreinte_courte_et_stable():
    pdf = b"%PDF-1.4 a"
    assert empreinte(pdf) == hashlib.sha256(pdf).hexdigest()[:8]
    assert empreinte(pdf) != empreinte(b"%PDF-1.4 b")

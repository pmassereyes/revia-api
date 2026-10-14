# test_logs.py - RevIA API
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
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
    finally:
        logger.setLevel(niveau_initial)


def test_empreinte_courte_et_stable():
    assert empreinte(b"%PDF-1.4 a") == empreinte(b"%PDF-1.4 a")
    assert empreinte(b"%PDF-1.4 a") != empreinte(b"%PDF-1.4 b")
    assert len(empreinte(b"%PDF-1.4 a")) == 8

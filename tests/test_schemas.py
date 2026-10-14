# test_schemas.py - RevIA API
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import QCMResponse

FIXTURE = Path(__file__).parent / "fixtures" / "reponse_exemple.json"


def test_fixture_valide():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rep = QCMResponse.model_validate(data)
    assert rep.qcm[0].index_bonne_reponse == 1


def test_index_hors_bornes():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["qcm"][0]["indexBonneReponse"] = 9
    with pytest.raises(ValidationError):
        QCMResponse.model_validate(data)


def test_avertissement_absent_vaut_null():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del data["avertissement"]
    rep = QCMResponse.model_validate(data)
    assert rep.avertissement is None
    assert rep.model_dump(by_alias=True)["avertissement"] is None


def test_avertissement_conserve():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["avertissement"] = "Document trop court pour 10 questions."
    rep = QCMResponse.model_validate(data)
    assert rep.avertissement == "Document trop court pour 10 questions."

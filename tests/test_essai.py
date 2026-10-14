# test_essai.py - RevIA API
import json
import re
from pathlib import Path

from scripts.essai import pdf_minimal, resume

FIXTURE = Path(__file__).parent / "fixtures" / "reponse_exemple.json"


def test_pdf_minimal_bien_forme():
    pdf = pdf_minimal("Bonjour")
    assert pdf.startswith(b"%PDF-")  # passe le contrôle de la route
    assert pdf.rstrip().endswith(b"%%EOF")
    assert b"(Bonjour) Tj" in pdf
    debut_xref = int(re.search(rb"startxref\n(\d+)\n", pdf).group(1))
    assert pdf[debut_xref:].startswith(b"xref")
    positions = re.findall(rb"(\d{10}) 00000 n ", pdf)
    assert len(positions) == 5
    for numero, position in enumerate(positions, start=1):
        assert pdf[int(position):].startswith(b"%d 0 obj" % numero)


def test_resume_de_la_fixture():
    lignes = resume(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert lignes[0].endswith("Questions obtenues : 1")
    assert lignes[1].endswith("Avertissement      : aucun")
    assert lignes[2].endswith("Thèmes             : Réseaux (1)")
    assert "     ✓ B. TCP" in lignes

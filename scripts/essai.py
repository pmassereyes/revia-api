# essai.py - RevIA API
"""Essai réel : envoie un PDF à l'API locale (make dev), qui appelle le vrai Gemini.

    make essai PDF=chemin/cours.pdf NB=10
    make essai-pauvre        # PDF d'une phrase : Gemini doit remplir « avertissement »

Le jeton est lu dans .env (API_TOKEN) et n'est jamais affiché.
"""
import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import httpx

from app.config import settings
from app.logs import empreinte

DOSSIER_ESSAIS = Path("essais")
PHRASE_PAUVRE = "Le protocole HTTP utilise par defaut le port 80."


def pdf_minimal(texte: str) -> bytes:
    """PDF valide d'une page contenant une seule ligne de texte (ASCII)."""
    contenu = f"BT /F1 12 Tf 72 720 Td ({texte}) Tj ET".encode("ascii")
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
            b" /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(contenu) + contenu + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    sortie = bytearray(b"%PDF-1.4\n")
    positions = []
    for numero, objet in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += b"%d 0 obj\n" % numero + objet + b"\nendobj\n"
    debut_xref = len(sortie)
    sortie += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1)
    for position in positions:
        sortie += b"%010d 00000 n \n" % position
    sortie += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objets) + 1,
        debut_xref,
    )
    return bytes(sortie)


def resume(qcm: dict) -> list[str]:
    """Lignes lisibles décrivant une réponse QCMResponse (JSON camelCase)."""
    questions = qcm["qcm"]
    themes = Counter(q["theme"] for q in questions)
    lignes = [
        f"  Questions obtenues : {len(questions)}",
        f"  Avertissement      : {qcm.get('avertissement') or 'aucun'}",
        "  Thèmes             : " + ", ".join(f"{t} ({n})" for t, n in themes.most_common()),
    ]
    exemple = questions[0]
    lignes.append(f"  Exemple            : {exemple['question']}")
    for i, proposition in enumerate(exemple["propositions"]):
        marque = "✓" if i == exemple["indexBonneReponse"] else " "
        lignes.append(f"     {marque} {chr(65 + i)}. {proposition}")
    return lignes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pdf", type=Path, help="PDF de cours à envoyer")
    source.add_argument("--pauvre", action="store_true", help="PDF d'une phrase, généré")
    parser.add_argument("--nb", type=int, default=10, help="nombre de questions demandé")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="adresse de l'API")
    args = parser.parse_args()

    if not settings.api_token:
        print("API_TOKEN est vide : copie .env.example en .env et renseigne-le.")
        return 2
    if args.pauvre:
        nom, pdf = "pauvre.pdf", pdf_minimal(PHRASE_PAUVRE)
    else:
        nom, pdf = args.pdf.name, args.pdf.read_bytes()

    print(f"POST {args.url}/v1/qcm : {nom}, {len(pdf) / 1024:.0f} Ko, {args.nb} questions demandées")
    # Pire cas côté API : toutes les tentatives Gemini, plus une marge
    delai = settings.gemini_timeout_s * settings.gemini_attempts + 30
    debut = time.perf_counter()
    try:
        reponse = httpx.post(
            f"{args.url}/v1/qcm",
            headers={"X-API-Token": settings.api_token},
            files={"file": (nom, pdf, "application/pdf")},
            data={"nb_questions": str(args.nb)},
            timeout=delai,
        )
    except httpx.ConnectError:
        print(f"API injoignable sur {args.url} : lance « make dev » dans un autre terminal.")
        return 1
    except httpx.TimeoutException:
        print(f"Pas de réponse après {delai} s.")
        return 1
    duree = time.perf_counter() - debut

    corps = reponse.json()
    if reponse.status_code != 200:
        print(f"→ {reponse.status_code} en {duree:.1f} s : {corps.get('code')} — {corps.get('message')}")
        print("  La cause détaillée est dans les journaux de l'API (lignes echec_gemini, erreur…).")
        return 1

    print(f"→ 200 en {duree:.1f} s")
    print("\n".join(resume(corps)))
    DOSSIER_ESSAIS.mkdir(exist_ok=True)
    fichier = DOSSIER_ESSAIS / f"{datetime.now():%Y%m%d-%H%M%S}-{empreinte(pdf)}.json"
    fichier.write_text(json.dumps(corps, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Réponse complète   : {fichier}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# melange.py - RevIA API
"""Ordre des propositions décidé par l'API : Gemini place trop souvent la bonne réponse en B.

L'ordre dépend uniquement du texte (tri sur SHA-256 de « question + proposition ») :
- déterministe : une même question donne toujours le même ordre ;
- idempotent : mélanger un QCM déjà mélangé ne change rien, d'où l'application sans risque
  aux QCM servis par le cache ;
- sans module random, inutile ici et signalé par Sonar comme point sensible.
"""
import hashlib

from app.schemas import QCMResponse, Question


def _rang(question: str, proposition: str) -> str:
    return hashlib.sha256(f"{question}\x00{proposition}".encode()).hexdigest()


def melanger_question(question: Question) -> Question:
    bonne_reponse = question.propositions[question.index_bonne_reponse]
    propositions = sorted(question.propositions, key=lambda p: _rang(question.question, p))
    return question.model_copy(
        update={
            "propositions": propositions,
            "index_bonne_reponse": propositions.index(bonne_reponse),
        }
    )


def melanger_propositions(qcm: QCMResponse) -> QCMResponse:
    return qcm.model_copy(update={"qcm": [melanger_question(q) for q in qcm.qcm]})

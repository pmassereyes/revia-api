# test_melange.py - RevIA API
from collections import Counter

from app.melange import melanger_propositions, melanger_question
from app.schemas import QCMResponse, Question


def question(propositions=("UDP", "TCP", "ICMP", "ARP"), index=1, texte="Quel protocole est fiable ?"):
    return Question(
        question=texte,
        propositions=list(propositions),
        index_bonne_reponse=index,
        explication="e",
        theme="Réseaux",
    )


def test_bonne_reponse_conservee():
    melangee = melanger_question(question())
    assert melangee.propositions[melangee.index_bonne_reponse] == "TCP"
    assert sorted(melangee.propositions) == ["ARP", "ICMP", "TCP", "UDP"]


def test_ordre_independant_de_celui_de_gemini():
    a = melanger_question(question(("UDP", "TCP", "ICMP", "ARP"), index=1))
    b = melanger_question(question(("ARP", "ICMP", "UDP", "TCP"), index=3))
    assert a == b


def test_idempotent():
    une_fois = melanger_question(question())
    assert melanger_question(une_fois) == une_fois


def test_positions_equilibrees():
    # 400 questions où Gemini aurait toujours mis la bonne réponse en B
    qcm = QCMResponse(qcm=[question(texte=f"Question {i} ?") for i in range(400)])
    positions = Counter(q.index_bonne_reponse for q in melanger_propositions(qcm).qcm)
    assert set(positions) == {0, 1, 2, 3}
    assert all(70 <= n <= 130 for n in positions.values()), positions


def test_avertissement_conserve():
    qcm = QCMResponse(qcm=[question()], avertissement="Document court.")
    assert melanger_propositions(qcm).avertissement == "Document court."

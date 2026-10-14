# test_prompt.py - RevIA API
from app.prompts.qcm import build_prompt


def test_prompt_demande_le_bon_nombre_de_questions():
    assert build_prompt(7).endswith("Génère exactement 7 questions.")


def test_prompt_sans_balises_de_gabarit():
    prompt = build_prompt(5)
    assert prompt.startswith("Tu es")
    assert "markdown.>" not in prompt


def test_prompt_avertissement_null_par_defaut():
    assert "laisse « avertissement » à null" in build_prompt(5)

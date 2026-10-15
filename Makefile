.PHONY: dev test coverage lint essai essai-pauvre

NB ?= 10

dev:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0

test:
	.venv/bin/pytest

# Rapports lus par SonarQube Cloud : coverage.xml et rapport-tests.xml
coverage:
	.venv/bin/pytest --cov --cov-report=term-missing --cov-report=xml --junitxml=rapport-tests.xml

lint:
	.venv/bin/ruff check .

# Essais réels avec la clé Gemini du .env (consomment le quota) ; lancer « make dev » à côté
essai:
	@test -n "$(PDF)" || (echo "Usage : make essai PDF=chemin/cours.pdf [NB=10]" && exit 2)
	.venv/bin/python -m scripts.essai --pdf "$(PDF)" --nb $(NB)

essai-pauvre:
	.venv/bin/python -m scripts.essai --pauvre --nb $(NB)

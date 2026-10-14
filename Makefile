.PHONY: dev test coverage lint

dev:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0

test:
	.venv/bin/pytest

# Rapports lus par SonarQube Cloud : coverage.xml et rapport-tests.xml
coverage:
	.venv/bin/pytest --cov --cov-report=term-missing --cov-report=xml --junitxml=rapport-tests.xml

lint:
	.venv/bin/ruff check .

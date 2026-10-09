.PHONY: dev test lint

dev:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
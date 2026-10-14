# Image de l'API RevIA, publiée sur ghcr.io par la CI (.github/workflows/ci-cd.yml)
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CACHE_DIR=/app/.cache

WORKDIR /app

# Utilisateur sans privilèges : le dossier du cache des QCM doit lui appartenir
RUN useradd --system --uid 10001 --no-create-home revia \
    && mkdir -p /app/.cache \
    && chown revia /app/.cache

# Dépendances d'abord, dans une couche séparée : elles ne sont réinstallées
# que si pyproject.toml change, pas à chaque modification du code
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/dependances.txt \
    && pip install -r /tmp/dependances.txt \
    && rm /tmp/dependances.txt

COPY app ./app
RUN pip install --no-deps . && rm -rf build ./*.egg-info

USER revia
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

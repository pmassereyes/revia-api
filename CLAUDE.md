# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

`revia-api` est le backend FastAPI de **RevIA**, une app iOS de révision par QCM (dépôt voisin `../revia-app`, Swift/SwiftUI). L'app envoie un cours en PDF. L'API le transmet à Gemini (`google-genai`) et renvoie un QCM.

- **On ne travaille que sur l'API.** `../revia-app` se lit pour comprendre le contrat, mais ne se modifie jamais. Un changement qui impacte l'app se signale dans la PR.
- **L'app n'appelle jamais Gemini.** `GEMINI_API_KEY` n'existe que côté serveur, dans `.env`.
- **L'app s'authentifie par un jeton partagé**, envoyé dans l'en-tête `X-API-Token` (`API_TOKEN` des deux côtés).
- En dev, l'app vise `http://<IP-du-Mac>:8000`. C'est pour ça que `make dev` écoute sur `0.0.0.0`.

## Circuit Git

Chaque changement suit ce circuit, sans exception :
1. Une issue GitHub.
2. Une branche `<n°>-<slug>` créée depuis `dev`.
3. Une PR vers `dev`, avec « Refs #n ».
4. Une PR `dev` → `main`, avec « Closes #n ». La fermeture automatique ne fonctionne que sur `main`, la branche par défaut.

Règles :
- Jamais de commit direct sur `dev` ni sur `main`.
- Claude merge lui-même les deux PR, une fois **tous** les checks verts, toujours avec un merge commit (`gh pr merge --merge`), jamais en squash : un squash ferait diverger `dev` et `main`.
- La branche de fonctionnalité est supprimée après son merge. On ne supprime jamais `dev`.
- Messages de commit en français (« Ajout de … (#n) »), sans trailer `Co-Authored-By`.

## Commandes

Le Python système (3.9) est trop ancien (`requires-python >= 3.11`). Le Makefile suppose un `.venv` à la racine :

```bash
uv venv && uv pip install -e ".[dev]"
cp .env.example .env          # GEMINI_API_KEY, API_TOKEN, GEMINI_MODEL, GEMINI_TIMEOUT_S, GEMINI_ATTEMPTS, MAX_PDF_MB, RATE_LIMIT_PER_MINUTE, CACHE_DIR, LOG_LEVEL

make dev                      # uvicorn --reload, 0.0.0.0:8000 ; Swagger sur /docs
make test                     # pytest
make coverage                 # pytest + coverage.xml + rapport-tests.xml (mêmes commandes qu'en CI)
make lint                     # ruff check, bloquant en CI

.venv/bin/pytest tests/test_qcm_route.py::test_rate_limit   # un seul test
.venv/bin/ruff check --fix .

docker compose up --build     # API dans un conteneur, construit en natif, lit .env
```

## API exposée

`POST /v1/qcm` reçoit un formulaire multipart : `file` (PDF) et `nb_questions` (1 à 30, 10 par défaut). `verify_token` s'exécute en dépendance. `rate_limit` est appelé au début de la route, donc après la validation : une requête rejetée en 401 ou 422 ne consomme pas le quota, alors qu'un rejet en 400 ou 413 le consomme.
- Succès : `QCMResponse`, soit `{"qcm": [{question, propositions, indexBonneReponse, explication, theme}], "avertissement": null}`. `avertissement` contient une phrase quand le document ne permet pas de produire le nombre de questions demandé.
- Erreur : toujours `{"code", "message"}`, y compris pour la validation et les erreurs imprévues, avec un code stable que l'app peut tester (`invalid_request` 422, `invalid_token` 401, `invalid_pdf` 400, `pdf_too_large` 413, `rate_limited` 429, `quota_exceeded` 429, `generation_failed` 502, `generation_timeout` 504, `provider_unavailable` 503 quand la clé Gemini est absente, `internal_error` 500). Les deux 429 se distinguent par `code` : `rate_limited` vient de la limite locale, `quota_exceeded` du quota Gemini.

`GET /health` sert de sonde.

## Architecture

Chaîne d'une requête : `routers/qcm.py` → `get_provider()` → `CachedProvider` → `GeminiProvider` → Gemini.

- **Provider** : `providers/base.py` définit `QCMProvider`, un `Protocol` (typage structurel, pas d'héritage). `GeminiProvider` envoie le PDF brut (`Part.from_bytes`) et le prompt, demande une sortie structurée (`response_schema=QCMResponse`), puis revalide la réponse avec Pydantic. Les `Field(description=...)` des schémas sont transmises à Gemini avec `response_schema` : elles font partie du prompt. Le client est configuré avec un délai maximal par tentative (`GEMINI_TIMEOUT_S`) et `GEMINI_ATTEMPTS` tentatives au total. Les nouvelles tentatives, gérées par `google-genai`, couvrent les 500 à 504, les dépassements de délai et les erreurs de connexion, mais pas les 429. Un 429 lève `QuotaExceededError`, un délai encore dépassé après toutes les tentatives `GenerationTimeoutError` (504), et toute autre erreur `GenerationFailedError`.
- **Assemblage** : `get_provider()` (dans `routers/qcm.py`, avec `@lru_cache`) construit le singleton `CachedProvider(GeminiProvider())`. Sans `GEMINI_API_KEY`, il lève `ProviderUnavailableError`. `lru_cache` ne mémorise pas les exceptions : la clé est revérifiée à chaque requête. Dans les tests qui appellent le vrai `get_provider`, appeler `get_provider.cache_clear()`. Un nouveau fournisseur ou un nouveau décorateur se branche ici.
- **Cache** (`cache.py`) : un fichier JSON par génération dans `CACHE_DIR`. La clé est le SHA-256 de `sha256(pdf) | nb_questions | gemini_model | PROMPT_VERSION`. L'écriture est atomique (`.tmp` puis `os.replace`), et un fichier illisible est supprimé puis régénéré. **Toute modification du prompt doit incrémenter `PROMPT_VERSION`** dans `prompts/qcm.py`, sinon le cache ressert les QCM de l'ancien prompt.
- **Rate limit** (`ratelimit.py`) : fenêtre glissante de 60 s, en mémoire, propre au processus, indexée par jeton. Il n'est pas déclaré en dépendance, car FastAPI exécute toutes les dépendances avant de signaler les erreurs de validation. Le jeton étant partagé par toutes les installations de l'app, la limite est en pratique globale.
- **Erreurs** (`errors.py`) : toute erreur destinée au client est une sous-classe de `ApiError` qui porte `status_code` et `code`. Le handler de `main.py` la convertit en `ErrorResponse`. On lève ces exceptions, jamais `HTTPException`. Deux autres handlers complètent le dispositif : `RequestValidationError` donne `invalid_request` (avec les champs en cause), et toute autre exception donne `internal_error`. Starlette relance alors l'exception, si bien que la trace reste dans les journaux du serveur.
- **Schémas** (`schemas.py`) : tous les modèles héritent de `CamelModel`, donc du snake_case côté Python et du camelCase dans le JSON (`by_alias=True` pour sérialiser). `Question` vérifie que `index_bonne_reponse` désigne bien une proposition.
- **Journaux** (`logs.py`) : `setup_logging()` configure le logger `app` au démarrage. Chaque module utilise `logging.getLogger(__name__)`. Le format est du texte `clé=valeur` (`generation …`, `cache=hit|miss …`, `echec_gemini …`, `reponse_gemini_invalide …`, `erreur code=… statut=…`). Un PDF s'identifie par `empreinte(pdf)` (8 caractères du SHA-256). **Ne jamais journaliser le contenu du PDF, la clé Gemini ni le jeton** : des tests le vérifient. Dans les tests, `caplog.set_level(logging.INFO, logger="app")`.
- **Config** (`config.py`) : singleton `settings` (pydantic-settings, lu depuis `.env`). Les valeurs sont lues à l'appel, pas à l'import. Toute nouvelle variable va dans `Settings` et dans `.env.example`.

## Tests

- Aucun test n'appelle Gemini. La route se teste avec `app.dependency_overrides[get_provider] = lambda: FakeProvider()`, le cache avec un faux provider qui compte ses appels. Les deux renvoient `tests/fixtures/reponse_exemple.json`. `GeminiProvider` se teste avec un faux client (`FakeModels`) injecté dans `provider._client`. Les erreurs Gemini se simulent avec `errors.ClientError` / `errors.ServerError(code, {...})`, et les erreurs réseau avec `httpx.ReadTimeout` / `httpx.ConnectError`.
- Les réglages se modifient par `monkeypatch.setattr(settings, ...)`. Le compteur de rate limit est global au module : appeler `ratelimit.reset()` dans les fixtures.
- Méthodes async testées hors route : `asyncio.run(...)`, sans plugin pytest-asyncio.

## CI/CD

Un seul workflow, `.github/workflows/ci-cd.yml` :

| Événement | `tests` (3.11, 3.14) | `sonar` | `image` |
|---|---|---|---|
| PR vers `dev` ou `main` | oui | oui | construction et test de démarrage, sans publication |
| Push sur `dev` | oui | non | publication `dev` + `sha-<commit>` |
| Push sur `main` | oui | oui | publication `latest` + `sha-<commit>` |

- **Sonar** (SonarQube Cloud, offre gratuite) : `main` est sa seule branche principale possible, et une analyse de `dev` serait refusée. `sonar.qualitygate.wait=true` fait échouer la pipeline si le Quality Gate échoue. Ce Quality Gate exige 80 % de couverture sur le code nouveau : chaque PR apporte ses tests. Les rapports (couverture, JUnit) sont produits par le job `tests` sous 3.11 et transmis en artefact.
- **Lint** : `make lint` tourne dans le job `tests` sous 3.11, et une erreur ruff fait échouer la pipeline.
- **Image** : `ghcr.io/pmassereyes/revia-api`, en `linux/amd64`. Le test de démarrage vérifie `/health`, puis qu'un `POST /v1/qcm` avec un jeton valide et un fichier non PDF renvoie 400. Un 500 trahirait un provider impossible à construire, par exemple un cache non accessible en écriture.
- Les actions sont figées par SHA, avec la version en commentaire. Pour en mettre une à jour, résoudre le SHA du nouveau tag (`gh api repos/<action>/git/ref/tags/<tag>`).
- Le `Dockerfile` installe les dépendances lues dans `pyproject.toml`, dans une couche séparée : une nouvelle dépendance n'y demande aucune modification. L'image tourne sous un utilisateur non root, avec le cache dans `/app/.cache`. `.dockerignore` est une liste blanche (`pyproject.toml` et `app/` seulement).

## Contrat avec l'app iOS

`tests/fixtures/reponse_exemple.json` est la référence du format de réponse. Son jumeau côté app, `../revia-app/RevIATests/Fixtures/reponse_exemple.json`, sert aux tests de décodage Swift. Les deux doivent rester identiques. Tout changement de `schemas.py` impose de mettre à jour la fixture ici, puis de signaler dans la PR la mise à jour à faire côté app (modèles `QCM`, `QuestionQCM`, `StatutGeneration`).

## Conventions

- Français pour les identifiants métier, les commentaires, les noms de tests (`test_pdf_trop_lourd`) et les messages d'erreur destinés à l'utilisateur.
- Chaque fichier Python commence par l'en-tête `# <fichier>.py - RevIA API`.
- Ruff avec `line-length = 100`, règles par défaut (dont I et B).
- Les paramètres FastAPI (`Depends`, `File`, `Form`, `Header`) se déclarent avec `Annotated[...]`. L'ancien style `x = Depends(...)` déclenche B008.

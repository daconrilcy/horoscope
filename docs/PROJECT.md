#! Horoscope Backend (FastAPI + Docker)

Backend FastAPI avec Docker Compose (API + Redis). Architecture DDD/Clean.

## Pré-requis
- Python 3.12+
- Docker + Docker Compose
- PowerShell (Windows) ou Bash (macOS/Linux)

## Démarrage rapide
- Docker (recommandé):
  - `docker compose -f docker/docker-compose.yml up --build`
  - API: http://localhost:8000 (Swagger: `/docs`, Redoc: `/redoc`)
- Local (hors Docker):
  - `python -m venv .venv && . .venv/Scripts/activate` (Windows) ou `. .venv/bin/activate` (Unix)
  - `pip install -r requirements.txt`
  - `cp .env.example .env`
  - Bash: `bash backend/scripts/dev.sh`
  - PowerShell: `./backend/scripts/dev.ps1`

## Scripts de dev
- `backend/scripts/dev.sh` (Bash)
  - Résout la racine du repo, auto-active `.venv` si présent, charge `.env`, ajoute `backend` au `PYTHONPATH`, lance `uvicorn app.main:app --reload`.
- `backend/scripts/dev.ps1` (PowerShell)
  - Équivalent Windows natif; auto-active `.venv` si présent; charge `.env` (supporte `export KEY=...` et commentaires inline non quotés). Si besoin: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
- Variables:
  - `HOST` (défaut: `0.0.0.0`) et `PORT` (défaut: `8000`) surchargent l'écoute.

## Docker Compose
Fichier: `docker/docker-compose.yml`
- Services:
  - `api`: FastAPI en reload, bind-mount du repo pour le dev, `PYTHONPATH=/app/backend` défini.
  - `redis`: Redis 7.
- Env: `.env.example` est chargé (ex: `REDIS_URL`, `CORS_ORIGINS`).

Commandes utiles:
- `docker compose -f docker/docker-compose.yml up --build`
- `docker compose -f docker/docker-compose.yml down -v` (arrêt + suppression des volumes)

## Tests
- `pytest -q` (le fichier `pytest.ini` pointe vers `backend/tests`)

## Arborescence
- `backend/api/` routes et schémas IO
- `backend/app/` création de l'app FastAPI
- `backend/core/` config, logging, DI
- `backend/domain/` modèles métier et services
- `backend/infra/` accès techniques (DB, cache, HTTP)
- `backend/middlewares/` middlewares
- `backend/tests/` tests
- `docker/` Dockerfile & docker-compose

## Endpoints utiles
- Health: `GET /health`
- Horoscope:
  - `POST /horoscope/natal` (payload naissance) → `{id, owner, chart}`
  - `GET /horoscope/today/{chart_id}` → leaders/influences/E-A-O/snippets/precision_score
  - `GET /horoscope/pdf/natal/{chart_id}` → PDF minimal
- Docs: `/docs` (Swagger), `/redoc` (Redoc)

Exemples curl
- `curl -s http://localhost:8000/health | jq .`

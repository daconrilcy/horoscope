# Horoscope Backend (FastAPI + Docker)

Backend FastAPI avec Docker Compose (API + Postgres + Redis). Structure inspirée DDD/Clean.

## Prérequis
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
  - `HOST` (défaut: `0.0.0.0`) et `PORT` (défaut: `8000`) surchargent l’écoute.

## Docker Compose
Fichier: `docker/docker-compose.yml`
- Services:
  - `api`: FastAPI en reload, bind-mount du repo pour le dev (profil `dev`).
  - `db`: Postgres 16 (volume `pgdata`, healthcheck `pg_isready`).
  - `redis`: Redis 7 (volume `redisdata`, healthcheck `redis-cli ping`).
- Dépendances: `api` attend que `db` et `redis` soient healthy.
- Env: `.env.example` est chargé (ex: `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`).

Commandes utiles:
- `docker compose -f docker/docker-compose.yml --profile dev up --build`
- `docker compose -f docker/docker-compose.yml down -v` (arrêt + suppression des volumes)

Profils:
- `dev`: services `api`, `db`, `redis` (reload + bind-mount)
- `prod`: service `api-prod` (sans bind-mount, sans reload) + `db`, `redis`

Exemples:
- Dev: `docker compose -f docker/docker-compose.yml --profile dev up --build`
- Prod: `docker compose -f docker/docker-compose.yml --profile prod up --build -d`

## Tests
- Unix/macOS: `PYTHONPATH=backend pytest -q`
- Windows PowerShell: `$env:PYTHONPATH='backend'; pytest -q`

## Arborescence
- `backend/api/` routes et schémas IO
- `backend/app/` création de l’app FastAPI
- `backend/core/` config, logging, DI
- `backend/domain/` modèles métier et services
- `backend/infra/` accès techniques (DB, cache, HTTP)
- `backend/middlewares/` middlewares
- `backend/tests/` tests
- `docker/` Dockerfile & docker-compose

## Endpoints utiles
- Health: `GET /health`
- Docs: `/docs` (Swagger), `/redoc` (Redoc)

Exemples curl
- `curl -s http://localhost:8000/health | jq .`

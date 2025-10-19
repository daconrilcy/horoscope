# Backend — Chat Conseiller (Phase 4)

## Démarrage
- `pip install -r requirements.txt`
- `make verify`

## Config
- `RETRIEVAL_BACKEND` in {faiss,weaviate,pinecone,elastic}

## Qualité
- `ruff check backend --fix && ruff format backend`
- `pytest -q` (cov ≥ 90%)

## Observabilité
- OTEL/Jaeger, Prometheus métriques (`backend/app/metrics.py`)
- Runbook : `backend/docs/observability_runbook.md`

## Migration Retrieval
- Doc : `backend/docs/retrieval_migration.md`


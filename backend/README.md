# Backend — Chat Conseiller (Phase 4)

## Démarrage
- `pip install -r requirements.txt`
- `make verify`

## Config
- `RETRIEVAL_BACKEND` in {faiss,weaviate,pinecone,elastic}
- Weaviate (recommandé pour #2) :
  - `WEAVIATE_URL` (ex: https://demo.weaviate.network)
  - `WEAVIATE_API_KEY` (si requis)
  - Endpoint utilisé: GraphQL `/v1/graphql` avec `nearText`.
  - Les erreurs réseau sont transformées en 502 par l'API.

## Qualité
- `ruff check backend --fix && ruff format backend`
- `pytest -q` (cov ≥ 90%)

## Observabilité
- OTEL/Jaeger, Prometheus métriques (`backend/app/metrics.py`)
- Runbook : `backend/docs/observability_runbook.md`

## Migration Retrieval
- Doc : `backend/docs/retrieval_migration.md`

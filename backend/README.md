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
 - Dual-write (#4): `RETRIEVAL_DUAL_WRITE=true` pour écrire dans FAISS + cible (best-effort).

## Qualité
- `ruff check backend --fix && ruff format backend`
- `pytest -q` (cov ≥ 90%)

## Observabilité
- OTEL/Jaeger, Prometheus métriques (`backend/app/metrics.py`)
- Runbook : `backend/docs/observability_runbook.md`

## Migration Retrieval
- Doc : `backend/docs/retrieval_migration.md`

## Bench – comment reproduire
- Générer un rapport local (ex: FAISS):
  - `python backend/scripts/bench_retrieval.py --adapter faiss --docs 10000 --qps 50 --topk 5`
  - Sortie: `artifacts/bench/<timestamp>_<adapter>.json` incluant p50/p95/QPS, RAM (si `psutil`), et SHA git.
- CI: Workflow "Retrieval Bench" (GitHub Actions) génère et uploade l'artefact JSON.

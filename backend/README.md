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

## Bench – comment reproduire
- Générer un rapport local (ex: FAISS):
  - `python backend/scripts/bench_retrieval.py --adapter faiss --docs 10000 --qps 50 --topk 5`
  - Sortie: `artifacts/bench/<timestamp>_<adapter>.json` incluant p50/p95/QPS, RAM (si `psutil`), et SHA git.
- CI: Workflow "Retrieval Bench" (GitHub Actions) génère et uploade l'artefact JSON.

## Embeddings – Workflow CI (#8)
- Déclenchement quand `content/**` ou `backend/infra/embeddings/**` change.
- Script: `python backend/scripts/build_embeddings.py`
  - Scanne `content/`, calcule un hash, génère des embeddings (local par défaut), écrit un artefact JSON sous `artifacts/embeddings/`.
  - Insère une ligne `ContentVersion` (SQLite par défaut en CI) avec `source=content/`, `version=<ts>` et `content_hash`.
- Workflow: `.github/workflows/embeddings.yml`
  - Secrets/permissions: `contents: read`, `actions: write` (upload-artifact). Si vous utilisez OpenAI, fournir `OPENAI_API_KEY`.

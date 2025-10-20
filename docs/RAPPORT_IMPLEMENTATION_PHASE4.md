# Rapport d’implémentation — Phase 4

Ce document synthétise l’implémentation réalisée à partir de `phase4_squelettes.mds`, ainsi que les vérifications de qualité (ruff) et d’exécution des tests (pytest).

## Contexte & Objectifs
- Mettre en place les squelettes fournis (services, API, scripts, docs, CI, observabilité, SLO/Coûts).
- Déplacer tous les tests dans `tests/` et rendre la configuration Pytest cohérente.
- Garantir que `ruff` ne signale aucune erreur et que `pytest -q` passe intégralement.

## Synthèse des changements
- Qualité/Dev:
  - `Makefile`: cibles `lint`, `test`, `typecheck`, `verify`.
  - `package.json`: scripts `lint`, `test`, `verify` (optionnels).
  - `.gitignore`: ajout de `.pytest_cache/`, `.ruff_cache/`, `artifacts/`, `TEMP*`.
- Retrieval Proxy & API:
  - `backend/services/retrieval_proxy.py`: proxy stateless + adaptateurs squelettes (FAISS, Weaviate, Pinecone, Elastic).
  - `backend/api/routes_retrieval.py`: endpoints internes `/internal/retrieval/embed` et `/internal/retrieval/search`.
- Bench & Migration:
  - `backend/scripts/bench_retrieval.py`: script de bench (placeholder mesurant latences simulées).
  - `backend/docs/retrieval_migration.md`: stratégie de migration FAISS → DB vectorielle.
- Gouvernance Contenu:
  - `backend/domain/content_version.py`: POPO `ContentVersion`.
  - `backend/infra/repo/content_version_repo.py`: repo CRUD (squelette, à relier à un ORM).
- LLM Guard & Vault:
  - `backend/app/middleware_llm_guard.py`: garde-fous entrée/contexte/sortie (squelettes à compléter).
  - `backend/infra/secrets/vault_client.py`: client Vault (placeholder).
- Celery & Monitoring:
  - `backend/app/celeryconfig.py`: configuration Celery générique.
  - `backend/tasks/utils.py`: utilitaire d’idempotence.
  - `backend/infra/monitoring/celery_exporter.py`: exporter Prometheus (squelette).
- Observabilité & SLO/Coûts:
  - `backend/app/metrics.py`: métriques Prometheus déjà existantes conservées.
  - `backend/docs/observability_runbook.md`, `backend/docs/grafana_dashboard.json`: runbook + dashboard exemple.
  - `backend/docs/slo.yaml`: SLOs et seuils budget.
  - `backend/app/cost_controls.py`: règles de budget et message dégradé.
- CI/CD:
  - `.github/workflows/embeddings.yml`: workflow pour régénération d’embeddings (squelette). Les workflows `ci.yml`/`release.yml` existants n’ont pas été modifiés.
- Documentation:
  - `backend/README.md`: instructions de démarrage, qualité, observabilité, migration.

## Déplacement et consolidation des tests
- Déplacement de tous les tests depuis `backend/tests/` vers `tests/`.
- Mises à jour:
  - `pytest.ini`: `testpaths = tests`.
  - `pyproject.toml` (ruff): `per-file-ignores` sur `tests/**/*.py`.
  - Imports corrigés, ex.: `tests/test_retrieval.py` → `from tests.fakes import FakeEmbeddings`.
  - `tests/test_bench_script.py`: exécution via module `python -m backend.scripts.bench_retrieval` pour éviter les imports relatifs.
- Suppression du dossier `backend/tests/` (réalisée côté repo).

## Nettoyage
- Suppression de fichiers temporaires:
  - `TEMP_head.txt`, `TEMP_head2.txt`, `TEMP_head3.txt`, `TEMP_head4.txt`, `TEMP_RUFF.txt`, `TEMP_show.txt`, `TEMP2.txt`.
- Suppression des artefacts de bench générés par les tests: `artifacts/bench/*` (et ajout de `artifacts/` dans `.gitignore`).

## Vérifications de qualité
- Ruff:
  - Commandes: `ruff check backend tests --fix` puis `ruff format backend tests`.
  - Résultat: aucun problème restant (All checks passed).
- Tests:
  - Commande: `pytest -q`.
  - Résultat: 17 passed.

## Exécution & Utilisation
- Lint & formatage: `make lint` (ou `npm run lint`).
- Tests: `make test` (ou `npm run test`).
- Vérification globale: `make verify` (ou `npm run verify`).
- Bench (manuel): `python -m backend.scripts.bench_retrieval --adapter faiss --docs 1000 --topk 5`.
- Variables d’environnement:
  - `RETRIEVAL_BACKEND` ∈ {`faiss`, `weaviate`, `pinecone`, `elastic`}.

## Points d’attention / TODOs
- Les adaptateurs de retrieval, garde-fous LLM, client Vault et repo SQL sont des squelettes: à implémenter au besoin.
- Le bench utilise des latences simulées: remplacer par un dataset réel et mesures précises.
- Ajouter le routeur retrieval à l’application principale si nécessaire (actuellement exposé par `backend/api/routes_retrieval.py` et utilisé dans les tests dédiés).
- Enrichir la migration (dual-write, shadow-read) et ajouter des tests d’agreement@k avant bascule.

---

Dernière exécution: ruff clean et `pytest -q` → 17 passed.

## Issue #18 — Documentation & DoD

- README: ajout des liens vers les artéfacts CI (bench JSON, embeddings) et le dashboard Grafana; ajout d’une checklist "Definition of Done" pour les PR.
- Runbooks: budgets/alertes SLO ajoutés dans `backend/docs/observability_runbook.md`; cutover/rollback couverts par `backend/docs/retrieval_migration.md`.
- SLOs: publication et références `slo.yaml` (+ mapping alertes Grafana/Prometheus via métriques existantes).

Références
- `README.md`
- `backend/docs/observability_runbook.md`
- `backend/docs/retrieval_migration.md`
- `backend/docs/grafana_dashboard.json`
- `slo.yaml`
- `artifacts/bench/`, `artifacts/embeddings/`

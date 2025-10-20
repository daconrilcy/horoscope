# Migration Retrieval — FAISS -> DB vectorielle

## Stratégie
- **Dual-write**: indexer dans FAISS **et** cible.

## Phase 4 — Cutover & Rollback (#6)

Critères de cutover (48h d'observation):
- P95 < 200 ms @ 10k documents (voir `backend/scripts/bench_retrieval.py`).
- agreement@5 ≥ 0.9 (métrique `retrieval_agreement_at_5{backend}`).
- 0 régression e2e (tests de fumée/chat OK, erreurs applicatives stables).

Processus (recommandé):
1. Activer `RETRIEVAL_DUAL_WRITE=true` et `RETRIEVAL_SHADOW_READ=true` (PCT=0.10).
2. Vérifier les métriques Prometheus/Grafana (dashboard `backend/docs/grafana_retrieval_dashboard.json`).
3. Si critères OK sur 48h: basculer `RETRIEVAL_BACKEND` vers la cible.
4. Après stabilisation, désactiver `RETRIEVAL_DUAL_WRITE`.

Scripts:
- `scripts/retrieval_cutover.sh`:
  - `--dry-run --target weaviate` affiche les changements sans modifier `.env`.
  - `--apply --target weaviate` active dual‑write + shadow‑read et commute `RETRIEVAL_BACKEND`.
  - `--rollback --previous faiss` restaure le backend précédent et coupe dual‑write/shadow.

SLO migration:
- RTO ≤ 30 min (capacité à revenir en arrière rapidement via `--rollback`).
- RPO ≤ 15 min (indexation idempotente; pertes limitées en cas de rollback).

Sécurité/Logs:
- Les clés API ne doivent jamais apparaître en clair (masquage systématique dans les logs).

- **Shadow-read**: comparer résultats en lecture, sans impacter l’utilisateur.
- **Agreement@k**: viser >= 0.9 avant bascule.
- **Feature flag**: bascule progressive par pourcentage de trafic.
- **Rollback**: < 10 minutes, scripté.

## Opérations
- **Backup/restore** index cible (RTO <= 30 min, RPO <= 15 min).
- **Warmup**: pré-chargement index (temps & RAM documentés).
- **Capacité**: QPS cible, P95, taille index, coûts.

## Validation
- Batteries de tests e2e + smoke tests post-déploiement.

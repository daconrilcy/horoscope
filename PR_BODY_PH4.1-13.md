# [PH4.1-13] Idempotency ack après commit (API→workers)

Issue: PH4.1-13 · Module: backend · Type: feature · Sévérité: P1 · Closes: #54
Branch: feat/PH4.1-13-idempotency-ack-apr-s-commit-api-workers

## Contexte
Accuser réception après commit DB et éviter doubles effets via idempotence côté worker.

## Scope
- Ajout utilitaire post-commit enqueue (API→workers) avec purge fiable sur rollback/savepoints
- Décorateur d’idempotence worker + clé canonique + verrous/états Redis
- Métriques producer/worker low-cardinality
- Réglages Celery (acks late, reject_on_worker_lost, prefetch=1)
- Tests unitaires ciblés (post-commit, savepoints, clé canonique, concurrence)
- Doc ops: `docs/ops/idempotency.md`

Hors scope: Transactional Outbox complète (documentée et recommandée)

## Acceptance Criteria
- Publication de tâches uniquement après COMMIT
- Idempotence côté worker avant effets de bord
- Ruff strict + mypy strict OK sur fichiers modifiés
- Tests verts et déterministes

## Feature Flags
- N/A (utilitaires infra activés par défaut)

## Tests
- `tests/infra/ops/test_post_commit.py` (commit/rollback/savepoints)
- `tests/tasks/test_task_idempotency.py` (duplicate, clé canonique, concurrence simulée)
- 463 tests verts localement

## Artefacts
- Doc: `docs/ops/idempotency.md` (clé canonique, métriques, Celery, runbook)

## Revue ops/qualité
- Validé: post-commit enqueue (pas d’émission sur rollback); décorateur d’idempotence sur worker
- Durcissements inclus:
  - Clé canonique JSON trié + normalisations (bytes→b64, sets triés, datetimes UTC)
  - Verrou `SETNX` Redis + TTL et états `in_progress/succeeded/failed`
  - Métriques producer: `postcommit_enqueue_total{result}`
  - Métriques worker: `worker_idempotency_attempts_total{task,result}`,
    `worker_idempotency_state_total{task,state}`
  - Réglages Celery: `acks_late`, `reject_on_worker_lost`, `prefetch=1`, `time_limit`
- Recommandé (optionnel): Transactional Outbox (table + dispatcher), script de rattrapage

## Risques & Rollback
1) Symptômes: pertes entre COMMIT→publish, doubles exécutions si clé mal formée
2) Actions: activer Outbox/dispatcher; rejouer manquants via runbook; revert PR si besoin
3) Vérif: métriques `postcommit_enqueue_total` et `worker_idempotency_*` stables; artefacts présents

## Checklist
- [x] `ruff` / `mypy` / `pytest`
- [x] Aucun `typing.List/Dict/Optional/Str`
- [x] Couverture tests périmètre OK
- [x] Docs/runbooks ajoutés

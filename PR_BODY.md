# [PH4.1-12] Timeouts/backoff au gateway + retry-budget

Issue: PH4.1-12 · Module: apigw · Type: task · Sévérité: P1 · Due: 2025-10-29
Branch: feat/PH4.1-12-timeouts-backoff-au-gateway-retry-budget

Closes #53

## Contexte
Uniformiser les timeouts au niveau du gateway, encadrer les retries (backoff + jitter) et limiter via un retry-budget par endpoint. Exposer des métriques pour le pilotage et documenter les entêtes contractuels.

## Scope (STRICT)
- Implémentation dans `backend/apigw/timeouts.py` et câblage dans `backend/app/main.py`.
- Aucune modification hors APIGW; pas de refactors transverses.

## Implémentation
- Middlewares ajoutés dans `backend/app/main.py`:
  - `HTTPServerMetricsMiddleware` déjà en place; ajout de `RetryMiddleware` puis `TimeoutMiddleware` (pour éviter le double comptage des retries).
- Politique par endpoint dans `ENDPOINT_TIMEOUTS` (timeouts, `max_retries`, `retry_budget_percent`).
- Budget de retry et backoff (exponentiel par défaut, jitter configurable).
- 4xx/429: pas de retry; 5xx transitoires (502/503) et timeouts: retry dans la limite du budget.
- En-têtes: `X-Timeout-Read`, `X-Timeout-Total`, `X-Max-Retries`; `Retry-After` fourni pour 429 (rate-limit/quota).
- Métriques: `apigw_retry_attempts_total{route,result}`, `apigw_retry_budget_exhausted_total{route}`.
- Doc: `docs/api/timeouts_backoff.md`.

## Tests
- Unitaires: `tests/apigw/test_timeouts.py` (config, backoff, budget, no-retry 4xx/429, retry 502/503, métriques).
- Rate-limit/quota 429 `Retry-After`: `tests/apigw/test_quota.py` (déjà présent).

## CI Gates
- Ruff strict ✅, mypy strict ✅, pytest ✅, ban typing aliases ✅.

## Risques & Rollback
1) Surconsommation de budget augmentant latence.
2) Action: revert PR.
3) Vérification: latences stables, métriques retry sous contrôle.

## Checklist
- [x] Scope respecté
- [x] Ruff + mypy OK
- [x] Aucun typing alias
- [x] Tests verts
- [x] PR ne référence qu’une seule issue

## [PH4.1-11] Metrics par endpoint (Prom) + traces corrélées

Issue: PH4.1-11
Branch: feat/PH4.1-11-metrics-par-endpoint-prom-traces-corr-l-es

## Contexte
Exposer `http_server_requests_seconds_bucket` et `http_server_requests_total` par route/method/status et propager `trace_id` via `X-Trace-ID` et logs structurés.

## Scope (STRICT)
- Implémentation observability au gateway (métriques HTTP par endpoint, traces corrélées).
- Hors scope: refactors transverses, timeouts/backoff, quotas.

## Implémentation
- Middlewares dans `backend/app/main.py`:
  - `TraceIdMiddleware`, `RequestLoggingMiddleware` (avant protections)
  - `HTTPServerMetricsMiddleware` (labels: route/method/status)
  - `PrometheusMiddleware` et route `/metrics` (déjà existants)
- Normalisation de route via `backend.app.metrics.normalize_route`.
- Aucun changement de contrat API; ajout de l’en-tête `X-Trace-ID` en réponse.

## Tests
- `tests/test_metrics.py`: expose `/metrics` et présence `http_server_requests_total`.
- `tests/apigw/test_http_metrics.py`: succès/500, méthodes HTTP, normalisation, params ignorés, durée, trace ID, concurrence, cohérence des labels.

## CI Gates
- Ruff strict ✅, mypy strict ✅, pytest ✅
- Ban typing aliases ✅ (aucun `typing.List/Dict/Optional/Str`)

## Risques & Rollback
1) Symptômes: cardinalité labels, surcoût latence middleware
2) Action: revert PR
3) Vérification: `/metrics` normal, logs OK

## Checklist
- [x] Scope respecté
- [x] Ruff + mypy OK
- [x] Aucun typing alias
- [x] Tests verts
- [x] PR ne référence qu’une seule issue



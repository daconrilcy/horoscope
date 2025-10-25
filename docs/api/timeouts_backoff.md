# Timeouts, backoff et retry-budget (API Gateway)

Ce document décrit la politique de timeouts et de backoff avec budget de retry au niveau du gateway.

## Principes

- Timeouts cohérents par endpoint via `backend/apigw/timeouts.py`.
- Retries autorisés uniquement sur erreurs transitoires (ex. 502/503) et timeouts.
- AUCUN retry sur 4xx/429.
- Budget de retry par endpoint: fraction du `total_timeout` (ex. 30%).
- Backoff configurable: exponentiel (défaut), linéaire, ou fixe, avec jitter.

## En-têtes de réponse

- `X-Timeout-Read`: budget de lecture prévu (s).
- `X-Timeout-Total`: timeout total prévu (s).
- `X-Max-Retries`: nombre de tentatives autorisées.
- `Retry-After`: présent uniquement pour 429 (rate-limit/quota), exprimé en secondes.

## Métriques (Prometheus)

- `apigw_retry_attempts_total{route,result="allowed|blocked"}`
- `apigw_retry_budget_exhausted_total{route}`
- `http_server_requests_seconds_bucket{route,method,status}` (latence par tentative)

## Configuration

- Par défaut dans `ENDPOINT_TIMEOUTS` (extraits):
  - `/v1/chat/answer`: total=15s, max_retries=2, retry_budget=20%
  - `/v1/retrieval/search`: total=10s, max_retries=3, retry_budget=30%
  - `/health`: total=3s, max_retries=1, retry_budget=10%

### Mise à jour à chaud (exemple)

```python
from backend.apigw.timeouts import configure_endpoint_timeout, TimeoutConfigUpdate

configure_endpoint_timeout(
    "/v1/chat/answer",
    config=TimeoutConfigUpdate(total_timeout=12.0, max_retries=3, retry_budget_percent=0.25),
)
```

## Ordre des middlewares

- `HTTPServerMetricsMiddleware` puis `RetryMiddleware` puis `TimeoutMiddleware` pour éviter de compter deux fois les retries côté métriques agrégées.

## Tests

- Voir `tests/apigw/test_timeouts.py`: stratégies de backoff, budget, 4xx/429 sans retry, 502/503 avec retry borné et métriques.



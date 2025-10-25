# Timeouts & Retries — API Gateway

## Objectif
Fournir un comportement cohérent et maîtrisé des timeouts et retries au niveau API Gateway :
- Deadline globale par requête (temps total maximum).
- Backoff exponentiel avec jitter par tentative.
- Retry-budget bornant le nombre/poids des tentatives.
- Whitelist stricte des erreurs retryables.
- Observabilité via métriques Prometheus low-cardinality.
- Entêtes contractuels côté client.

---

## Modèle de temps
- Deadline globale: le Gateway calcule `deadline = now + X-Timeout-Total`.
  Chaque tentative vérifie le temps restant; si `<= 0`, le retry est bloqué (`reason=deadline_exceeded`).
- Read timeout par tentative: `min(X-Timeout-Read, temps_restant)`.
- Clamps: les valeurs effectives sont bornées par la configuration (max absolus).

Important: aucun header client ne peut augmenter les timeouts. Les valeurs sont côté serveur.

---

## Politique de retry
- Retryables:
  - Timeout de connexion/lecture,
  - 502, 503 (transitoires).
- Non-retryables:
  - 4xx (400/401/403/409),
  - 429 (respecter `Retry-After` côté client),
  - 500, 504 (par défaut).
- Budget:
  - Limite de tentatives par endpoint (ex. `max_retries`) et/ou pourcentage de budget (`retry_budget_percent`).
  - Si budget atteint → blocage `reason=budget_exhausted`.

---

## Entêtes de réponse
- `X-Timeout-Read`: read timeout effectif (s).
- `X-Timeout-Total`: total timeout effectif (s).
- `X-Max-Retries`: nombre max de retries autorisés pour l’endpoint.
- `X-Retry-Count`: nombre de tentatives effectivement réalisées (0 = aucun retry).
- `Retry-After` (seulement pour 429): délai recommandé (secondes).

---

## Métriques Prometheus
Labels stables, pas de tenant en labels.

- Durée HTTP  
  `http_server_requests_seconds_bucket{route,method,status,le}`  
  Buckets SLO-like: `[0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 2.0]`.

- Volume HTTP  
  `http_server_requests_total{route,method,status}`

- Retries  
  `apigw_retry_attempts_total{route,result="allowed|blocked"}`  
  `apigw_retry_budget_exhausted_total{route}`  
  `apigw_retry_blocks_total{route,reason="non_retryable|deadline_exceeded|budget_exhausted"}`

### PromQL utiles
```promql
sum(rate(apigw_retry_attempts_total{result="allowed"}[5m])) by (route)
sum(rate(apigw_retry_blocks_total[5m])) by (route, reason)
sum(rate(apigw_retry_budget_exhausted_total[15m])) by (route)
histogram_quantile(0.95, sum(rate(http_server_requests_seconds_bucket[5m])) by (le,route))
```

### Exemples cURL
Succès sans retry
```bash
curl -i https://api.example.com/v1/chat/answer
# X-Timeout-Read, X-Timeout-Total, X-Max-Retries, X-Retry-Count: 0
```

429 (rate-limit/quota)
```bash
curl -i https://api.example.com/v1/chat/answer
# HTTP/1.1 429 Too Many Requests
# Retry-After: 12
# X-Retry-Count: 0
# Body: {"code":"RATE_LIMITED","message":"...","trace_id":"..."}
```

Erreur transitoire (retry effectué)
```bash
curl -i https://api.example.com/v1/horoscope/generate
# X-Retry-Count: 1    # une tentative de retry a été effectuée
```

### Notes CDN (optionnel)
Si un CDN/edge est présent, le Gateway peut ajouter pour certaines réponses (ex. 410 Gone post-sunset) :

```
Surrogate-Control: max-age=60
Cache-Control: max-age=60, must-revalidate
```

Ces entêtes sont gérés par flag côté Gateway et n’affectent pas les timeouts/retries.

### Sécurité
- Pas de propagation de timeouts depuis le client.
- Pas de PII en labels Prometheus; `trace_id` pour corrélation via logs.
- Jitter activé pour éviter la synchronisation des retries.

### Tableau (exemple)

Endpoint | Read (s) | Total (s) | Max Retries | Retryables | Non-retryables
---|---:|---:|---:|---|---
GET /v1/chat/answer | 3 | 5 | 2 | timeout, 502,503 | 4xx, 429, 500, 504
POST /v1/chat/answer | 5 | 8 | 2 | timeout, 502,503 | 4xx, 429, 500, 504

(Les valeurs effectives dépendent de la configuration `ENDPOINT_TIMEOUTS`.)

### Changelog
- Ajout deadline globale et consommation du temps restant par tentative.
- Exposition `X-Retry-Count`.
- Nouvelle métrique `apigw_retry_blocks_total{route,reason}`.
- Clarification whitelist/blacklist d’erreurs retryables.
- PromQL d’observabilité et exemples cURL.

---

### Prochain pas
- Poster le commentaire PR associé et ajouter ce fichier doc.
- Lancer la CI; en staging, vérifier `X-Retry-Count` et la stabilité du P95.
- Un runbook incident “tempête de retries” peut être ajouté (signaux, actions, rollback).

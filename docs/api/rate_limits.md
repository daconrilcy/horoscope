# Rate Limiting & Quotas API

Cette documentation décrit la politique de rate limiting et de quotas appliquée par l'API Gateway.

## Vue d'ensemble

L'API Gateway applique des limites de taux et des quotas pour protéger les ressources et garantir une utilisation équitable du service.

### Types de limites

1. **Rate Limiting** : Limite le nombre de requêtes par fenêtre de temps
2. **Quotas** : Limite l'utilisation de ressources spécifiques par endpoint

## Rate Limiting

### Configuration par défaut

- **Fenêtre** : 60 secondes
- **Limite** : 60 requêtes par fenêtre
- **Algorithme** : Fenêtre glissante atomique (Redis)

### Comportement

- Les requêtes sont comptées par tenant et par route
- Le tenant est extrait depuis le JWT (source de vérité)
- Les headers `X-Tenant-ID` ne sont acceptés que pour le trafic interne
- En cas de dépassement, une réponse `429 Too Many Requests` est retournée

### Headers de réponse

#### Requêtes autorisées

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

#### Requêtes bloquées

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995200
```

## Quotas par endpoint

### Endpoints avec quotas

#### Chat (`/v1/chat/*`)

- **Ressource** : `chat_requests_per_hour`
- **Limite** : Configurable par tenant
- **Comportement** : Blocage avec `429` si quota dépassé

#### Retrieval (`/v1/retrieval/*`)

- **Ressource** : `retrieval_requests_per_hour`
- **Limite** : Configurable par tenant
- **Comportement** : Blocage avec `429` si quota dépassé

### Endpoints exemptés

Les endpoints suivants ne sont pas soumis au rate limiting :

- `/health` - Health checks
- `/metrics` - Métriques Prometheus
- `/docs` - Documentation API
- `/openapi.json` - Schéma OpenAPI

## Réponses d'erreur

### Format standard

Toutes les erreurs suivent le format d'enveloppe d'erreur standard :

```json
{
  "code": "RATE_LIMITED",
  "message": "Rate limit exceeded. Try again later.",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "retry_after": 30
  }
}
```

### Codes d'erreur

- `RATE_LIMITED` : Limite de taux dépassée
- `QUOTA_EXCEEDED` : Quota de ressource dépassé

### Headers d'erreur

- `Retry-After` : Nombre de secondes à attendre avant de réessayer (entier ≥ 1)

## Exemples d'utilisation

### Requête dans la limite

```bash
curl -H "Authorization: Bearer <jwt-token>" \
     -H "Content-Type: application/json" \
     https://api.example.com/v1/chat/message \
     -d '{"message": "Hello"}'
```

**Réponse :**
```
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1640995200

{"response": "Hello back!"}
```

### Requête bloquée par rate limit

```bash
curl -H "Authorization: Bearer <jwt-token>" \
     -H "Content-Type: application/json" \
     https://api.example.com/v1/chat/message \
     -d '{"message": "Hello"}'
```

**Réponse :**
```
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995200

{
  "code": "RATE_LIMITED",
  "message": "Rate limit exceeded. Try again later.",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "retry_after": 45
  }
}
```

### Requête bloquée par quota

```bash
curl -H "Authorization: Bearer <jwt-token>" \
     -H "Content-Type: application/json" \
     https://api.example.com/v1/chat/message \
     -d '{"message": "Hello"}'
```

**Réponse :**
```
HTTP/1.1 429 Too Many Requests
Retry-After: 3600
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995200

{
  "code": "QUOTA_EXCEEDED",
  "message": "Quota exceeded for chat requests",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "retry_after": 3600
  }
}
```

## Gestion des erreurs côté client

### Stratégies recommandées

1. **Respecter `Retry-After`** : Attendre le délai indiqué avant de réessayer
2. **Backoff exponentiel** : Augmenter progressivement les délais entre tentatives
3. **Circuit breaker** : Arrêter temporairement les requêtes en cas d'erreurs répétées

### Exemple d'implémentation

```python
import time
import requests

def make_request_with_retry(url, headers, data, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 1))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)  # Backoff exponentiel
    
    raise Exception("Max retries exceeded")
```

## Observabilité

### Métriques Prometheus

Les métriques suivantes sont disponibles pour le monitoring :

- `apigw_rate_limit_decisions_total{route,result}` : Décisions de rate limiting
- `apigw_rate_limit_blocks_total{route,reason}` : Requêtes bloquées par raison
- `apigw_rate_limit_evaluation_seconds{route}` : Temps d'évaluation des limites
- `apigw_rate_limit_near_limit_total{route}` : Requêtes proches de la limite
- `apigw_tenant_spoof_attempts_total{route}` : Tentatives de spoof de tenant

### Logs JSON

Les logs incluent les informations suivantes (sans PII) :

```json
{
  "level": "warning",
  "message": "Rate limit exceeded",
  "tenant": "tenant123",
  "tenant_source": "jwt",
  "spoof": false,
  "route": "/v1/chat/{id}",
  "method": "POST",
  "retry_after": 30,
  "trace_id": "abc123-def456-ghi789",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Sécurité

### Trust Model

- **JWT** : Source de vérité pour l'identité du tenant
- **Headers internes** : `X-Tenant-ID` accepté uniquement pour le trafic interne
- **Détection de spoof** : Tentatives de contournement détectées et tracées

### Headers internes

Les headers suivants sont réservés au trafic interne :

- `X-Internal-Auth` : Token d'authentification interne
- `X-Service-Mesh` : Identité du service mesh

## Configuration

### Variables d'environnement

```bash
# Redis pour le rate limiting distribué
REDIS_URL=redis://localhost:6379/0

# Configuration des limites
RL_WINDOW_SECONDS=60
RL_MAX_REQ_PER_WINDOW=60

# Timeouts Redis
RL_CONNECT_TIMEOUT_MS=100
RL_READ_TIMEOUT_MS=100
```

### Configuration par tenant

Les quotas peuvent être configurés par tenant via l'API d'administration ou la configuration.

## Support

Pour toute question sur les rate limits et quotas :

1. Consultez les métriques Prometheus pour diagnostiquer les problèmes
2. Vérifiez les logs JSON pour les détails des blocages
3. Contactez l'équipe de support avec le `trace_id` en cas de problème

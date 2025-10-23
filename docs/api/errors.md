# API Error Handling

Cette documentation décrit le format des erreurs retournées par l'API et les codes d'erreur disponibles.

## Format d'erreur standard

Toutes les erreurs API suivent un format d'enveloppe d'erreur cohérent :

```json
{
  "code": "ERROR_CODE",
  "message": "Description humaine de l'erreur",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "additional": "information"
  }
}
```

### Champs de l'enveloppe d'erreur

- `code` (string) : Code d'erreur unique et stable
- `message` (string) : Description humaine de l'erreur
- `trace_id` (string, optionnel) : Identifiant de traçage pour le debugging
- `details` (object, optionnel) : Informations supplémentaires spécifiques à l'erreur

## Codes d'erreur HTTP

### 4xx - Erreurs client

#### 400 Bad Request

```json
{
  "code": "INVALID_REQUEST",
  "message": "The request is invalid or malformed",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "field": "message",
    "reason": "required field missing"
  }
}
```

#### 401 Unauthorized

```json
{
  "code": "UNAUTHORIZED",
  "message": "Authentication required",
  "trace_id": "abc123-def456-ghi789"
}
```

#### 403 Forbidden

```json
{
  "code": "FORBIDDEN",
  "message": "Access denied",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "reason": "insufficient_permissions"
  }
}
```

#### 404 Not Found

```json
{
  "code": "NOT_FOUND",
  "message": "Resource not found",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "resource": "chat",
    "id": "123"
  }
}
```

#### 429 Too Many Requests

**Rate Limit Exceeded :**

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

**Quota Exceeded :**

```json
{
  "code": "QUOTA_EXCEEDED",
  "message": "Quota exceeded for chat requests",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "retry_after": 3600,
    "resource": "chat_requests_per_hour"
  }
}
```

### 5xx - Erreurs serveur

#### 500 Internal Server Error

```json
{
  "code": "INTERNAL_ERROR",
  "message": "An internal error occurred",
  "trace_id": "abc123-def456-ghi789"
}
```

#### 502 Bad Gateway

```json
{
  "code": "BAD_GATEWAY",
  "message": "Upstream service unavailable",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "service": "llm-service"
  }
}
```

#### 503 Service Unavailable

```json
{
  "code": "SERVICE_UNAVAILABLE",
  "message": "Service temporarily unavailable",
  "trace_id": "abc123-def456-ghi789",
  "details": {
    "retry_after": 60
  }
}
```

## Headers d'erreur spéciaux

### Rate Limiting

Pour les erreurs `429`, les headers suivants sont inclus :

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995200
```

#### Description des headers

- `Retry-After` : Nombre de secondes à attendre avant de réessayer (entier ≥ 1)
- `X-RateLimit-Limit` : Limite totale de requêtes par fenêtre
- `X-RateLimit-Remaining` : Nombre de requêtes restantes dans la fenêtre actuelle
- `X-RateLimit-Reset` : Timestamp Unix de la fin de la fenêtre actuelle

### Traçage

Pour toutes les erreurs, le header suivant peut être inclus :

```
X-Trace-Id: abc123-def456-ghi789
```

## Codes d'erreur spécifiques

### Rate Limiting & Quotas

| Code | Description | Détails |
|------|-------------|---------|
| `RATE_LIMITED` | Limite de taux dépassée | `retry_after` (secondes) |
| `QUOTA_EXCEEDED` | Quota de ressource dépassé | `retry_after`, `resource` |

### Authentification & Autorisation

| Code | Description | Détails |
|------|-------------|---------|
| `UNAUTHORIZED` | Token manquant ou invalide | - |
| `FORBIDDEN` | Permissions insuffisantes | `reason` |
| `TENANT_SPOOF_DETECTED` | Tentative de spoof de tenant | `detected_source` |

### Validation

| Code | Description | Détails |
|------|-------------|---------|
| `INVALID_REQUEST` | Requête malformée | `field`, `reason` |
| `VALIDATION_ERROR` | Erreur de validation | `field`, `constraint` |

### Ressources

| Code | Description | Détails |
|------|-------------|---------|
| `NOT_FOUND` | Ressource introuvable | `resource`, `id` |
| `CONFLICT` | Conflit de ressource | `resource`, `reason` |

### Services

| Code | Description | Détails |
|------|-------------|---------|
| `SERVICE_UNAVAILABLE` | Service temporairement indisponible | `service`, `retry_after` |
| `BAD_GATEWAY` | Service en amont indisponible | `service` |
| `TIMEOUT` | Timeout de requête | `service`, `timeout_ms` |

## Gestion des erreurs côté client

### Stratégies recommandées

1. **Respecter les codes d'erreur** : Traiter chaque code spécifiquement
2. **Utiliser `Retry-After`** : Attendre le délai indiqué pour les erreurs temporaires
3. **Implémenter un circuit breaker** : Arrêter les requêtes en cas d'erreurs répétées
4. **Logger le `trace_id`** : Faciliter le debugging avec l'équipe de support

### Exemple d'implémentation

```python
import time
import requests
from typing import Dict, Any

class APIError(Exception):
    def __init__(self, code: str, message: str, trace_id: str = None, details: Dict[str, Any] = None):
        self.code = code
        self.message = message
        self.trace_id = trace_id
        self.details = details or {}
        super().__init__(f"{code}: {message}")

def handle_api_response(response: requests.Response) -> Dict[str, Any]:
    """Handle API response and raise appropriate exceptions."""
    if response.status_code == 200:
        return response.json()
    
    try:
        error_data = response.json()
    except ValueError:
        response.raise_for_status()
    
    code = error_data.get('code', 'UNKNOWN_ERROR')
    message = error_data.get('message', 'Unknown error')
    trace_id = error_data.get('trace_id')
    details = error_data.get('details', {})
    
    # Handle specific error codes
    if code == 'RATE_LIMITED':
        retry_after = details.get('retry_after', 1)
        raise RateLimitError(code, message, trace_id, details, retry_after)
    elif code == 'QUOTA_EXCEEDED':
        retry_after = details.get('retry_after', 3600)
        raise QuotaExceededError(code, message, trace_id, details, retry_after)
    elif code in ['UNAUTHORIZED', 'FORBIDDEN']:
        raise AuthenticationError(code, message, trace_id, details)
    elif response.status_code >= 500:
        raise ServerError(code, message, trace_id, details)
    else:
        raise APIError(code, message, trace_id, details)

class RateLimitError(APIError):
    def __init__(self, code: str, message: str, trace_id: str, details: Dict[str, Any], retry_after: int):
        super().__init__(code, message, trace_id, details)
        self.retry_after = retry_after

class QuotaExceededError(APIError):
    def __init__(self, code: str, message: str, trace_id: str, details: Dict[str, Any], retry_after: int):
        super().__init__(code, message, trace_id, details)
        self.retry_after = retry_after

class AuthenticationError(APIError):
    pass

class ServerError(APIError):
    pass

# Usage example
def make_request_with_retry(url: str, headers: Dict[str, str], data: Dict[str, Any], max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            return handle_api_response(response)
            
        except RateLimitError as e:
            print(f"Rate limited. Waiting {e.retry_after} seconds...")
            time.sleep(e.retry_after)
            
        except QuotaExceededError as e:
            print(f"Quota exceeded. Waiting {e.retry_after} seconds...")
            time.sleep(e.retry_after)
            
        except AuthenticationError as e:
            print(f"Authentication error: {e.message}")
            raise  # Don't retry auth errors
            
        except ServerError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    
    raise Exception("Max retries exceeded")
```

## Debugging

### Utilisation du trace_id

Le `trace_id` permet de tracer une requête à travers tous les services :

1. **Côté client** : Logger le `trace_id` avec chaque erreur
2. **Côté support** : Utiliser le `trace_id` pour rechercher dans les logs
3. **Côté développement** : Corréler les logs entre services

### Recherche dans les logs

```bash
# Rechercher par trace_id
grep "abc123-def456-ghi789" /var/log/api/*.log

# Rechercher les erreurs d'un tenant
grep '"tenant":"tenant123"' /var/log/api/*.log | grep ERROR

# Rechercher les rate limits
grep "RATE_LIMITED" /var/log/api/*.log
```

## Évolution des erreurs

### Compatibilité

- Les codes d'erreur sont stables et ne changent pas
- Les nouveaux champs dans `details` sont ajoutés de manière additive
- Les champs existants ne sont jamais supprimés

### Ajout de nouveaux codes

1. Documenter le nouveau code dans cette page
2. Ajouter les tests correspondants
3. Mettre à jour les clients avec la gestion du nouveau code

## Support

Pour toute question sur la gestion des erreurs :

1. Consultez cette documentation pour les codes d'erreur
2. Vérifiez les logs avec le `trace_id` fourni
3. Contactez l'équipe de support avec le `trace_id` et le code d'erreur

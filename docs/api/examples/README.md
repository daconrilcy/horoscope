# API Examples

Ce répertoire contient des exemples d'utilisation de l'API avec gestion des rate limits et quotas.

## Fichiers disponibles

### `test_rate_limits.sh`
Script bash pour tester les rate limits avec cURL.

**Utilisation :**
```bash
# Modifier les variables en haut du script
API_BASE_URL="https://api.example.com"
JWT_TOKEN="your-jwt-token-here"

# Exécuter le script
chmod +x test_rate_limits.sh
./test_rate_limits.sh
```

**Tests inclus :**
- Requête normale (dans la limite)
- Dépassement de rate limit
- Test avec headers de tenant
- Test avec trafic interne
- Test endpoint exempté (/health)
- Test quota retrieval
- Test avec JWT invalide
- Test de respect du Retry-After

### `api_client_example.py`
Client Python avec gestion automatique des rate limits.

**Utilisation :**
```python
from api_client_example import APIClient

# Créer le client
client = APIClient("https://api.example.com", "your-jwt-token")

# Envoyer un message de chat
response = client.send_chat_message("Hello!")

# Effectuer une recherche
results = client.search_retrieval("test query", limit=10)
```

**Fonctionnalités :**
- Gestion automatique des erreurs 429
- Respect du header Retry-After
- Backoff exponentiel pour les erreurs serveur
- Parsing des headers de rate limiting
- Retry automatique avec limite configurable

## Configuration requise

### Variables d'environnement

```bash
# URL de base de l'API
export API_BASE_URL="https://api.example.com"

# Token JWT pour l'authentification
export JWT_TOKEN="your-jwt-token-here"
```

### Dépendances Python

```bash
pip install requests
```

## Exemples de réponses

### Requête autorisée

```json
{
  "response": "Hello back!"
}
```

**Headers :**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1640995200
```

### Requête bloquée (Rate Limit)

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

**Headers :**
```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995200
```

### Requête bloquée (Quota)

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

## Monitoring et debugging

### Métriques Prometheus

Surveillez ces métriques pour diagnostiquer les problèmes :

```promql
# Décisions de rate limiting
sum(rate(apigw_rate_limit_decisions_total[5m])) by (route, result)

# Requêtes bloquées
sum(rate(apigw_rate_limit_blocks_total[5m])) by (route, reason)

# Tentatives de spoof
sum(rate(apigw_tenant_spoof_attempts_total[15m])) by (route)
```

### Logs

Recherchez dans les logs avec le `trace_id` :

```bash
# Rechercher par trace_id
grep "abc123-def456-ghi789" /var/log/api/*.log

# Rechercher les rate limits
grep "RATE_LIMITED" /var/log/api/*.log

# Rechercher les spoof attempts
grep "spoof" /var/log/api/*.log
```

## Bonnes pratiques

### Côté client

1. **Respecter Retry-After** : Attendre le délai indiqué avant de réessayer
2. **Implémenter un circuit breaker** : Arrêter les requêtes en cas d'erreurs répétées
3. **Logger le trace_id** : Faciliter le debugging avec l'équipe de support
4. **Backoff exponentiel** : Augmenter progressivement les délais entre tentatives

### Côté serveur

1. **Monitoring** : Surveiller les métriques de rate limiting
2. **Alerting** : Configurer des alertes pour les spikes de 429
3. **Logs** : S'assurer que les logs incluent le trace_id
4. **Configuration** : Ajuster les limites selon l'usage observé

## Support

Pour toute question sur l'utilisation de l'API :

1. Consultez la documentation des [rate limits](../rate_limits.md) et [erreurs](../errors.md)
2. Vérifiez les logs avec le `trace_id` fourni
3. Contactez l'équipe de support avec le `trace_id` et le code d'erreur
4. Utilisez les exemples fournis comme référence

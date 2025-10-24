# Politique de versioning et de dépréciation des API

## Vue d'ensemble

Ce document décrit la politique de versioning et de dépréciation des API pour le projet Astro, conforme aux RFC 9745 (Deprecation HTTP Header) et RFC 8594 (Sunset HTTP Header).

## Versioning

### Préfixe `/v1`

Toutes les routes API métier sont préfixées par `/v1` :

- `/v1/auth/*` - Routes d'authentification
- `/v1/horoscope/*` - Routes d'horoscope
- `/v1/chat/*` - Routes de chat

### Routes système

Les routes système ne sont **pas** versionnées :

- `/health` - Endpoint de santé
- `/metrics` - Métriques Prometheus
- `/docs` - Documentation OpenAPI
- `/openapi.json` - Spécification OpenAPI

## Dépréciation des routes legacy

### Routes legacy supportées

Les routes legacy suivantes sont interceptées et redirigées vers leurs équivalents `/v1` :

- `/auth/*` → `/v1/auth/*`
- `/horoscope/*` → `/v1/horoscope/*`
- `/chat/*` → `/v1/chat/*`

### Codes de statut

Conforme à RFC 7231 et MDN Web Docs, les codes de redirection dépendent de la méthode HTTP :

- **GET/HEAD** : `301 Moved Permanently`
- **POST/PUT/PATCH/DELETE** : `308 Permanent Redirect` (préserve la méthode et le body)

### Headers de dépréciation

Conforme aux RFC 9745 et RFC 8594 :

```http
Deprecation: @1761264000
Sunset: Wed, 31 Dec 2025 23:59:59 GMT
Warning: 299 - "Deprecated API. Use /v1/auth/login"
Location: /v1/auth/login
Link: </v1/auth/login>; rel="successor-version", <https://docs.astro.com/api/versioning>; rel="deprecation"
Cache-Control: public, max-age=86400
```

#### `Deprecation` (RFC 9745)

Format : Unix timestamp préfixé par `@`

Exemple : `@1761264000` (2025-10-24 00:00:00 UTC)

#### `Sunset` (RFC 8594)

Format : HTTP-date (IMF-fixdate)

Exemple : `Wed, 31 Dec 2025 23:59:59 GMT`

Contrainte : `Sunset` ≥ `Deprecation`

#### `Link` (RFC 8288 + RFC 9745)

Deux relations :

- `rel="successor-version"` : Pointe vers la nouvelle route
- `rel="deprecation"` : Pointe vers la documentation de dépréciation

### Réponse JSON

```json
{
  "code": "DEPRECATED_ROUTE",
  "message": "Cette route est dépréciée et sera supprimée le 2025-12-31. Utilisez /v1/auth/login",
  "trace_id": "abc123",
  "deprecation": {
    "sunset_date": "2025-12-31",
    "new_path": "/v1/auth/login",
    "warning": "Cette route sera supprimée le 2025-12-31"
  }
}
```

## Métriques

### `apigw_legacy_hits_total`

Compteur Prometheus (low-cardinality) :

```promql
apigw_legacy_hits_total{route="/auth", method="POST"}
```

Labels :

- `route` : Préfixe legacy (`/auth`, `/horoscope`, `/chat`)
- `method` : Méthode HTTP (`GET`, `POST`, etc.)

**Note** : Pas de label `tenant` pour éviter la haute cardinalité.

### Requêtes PromQL utiles

**Usage legacy encore élevé** :

```promql
sum(rate(apigw_legacy_hits_total[1h])) by (route) > 1
```

**Proportion de redirections** :

```promql
sum(rate(http_responses_total{status=~"30[18]"}[5m])) by (route)
/ sum(rate(http_responses_total[5m])) by (route) > 0.2
```

## Observabilité

### Logs structurés

Tous les accès aux routes legacy sont loggés avec structlog :

```python
log.warning(
    "legacy_route_access",
    legacy_path="/auth/login",
    new_path="/v1/auth/login",
    client_ip="192.168.1.1",
    user_agent="curl/7.68.0",
)
```

### Dashboard Grafana

Créer un panneau pour suivre la décroissance du trafic legacy :

```promql
sum(rate(apigw_legacy_hits_total[1h])) by (route)
```

## Comportement post-sunset

Après la date de sunset (2025-12-31), les routes legacy retourneront :

- **Code de statut** : `410 Gone`
- **Message** : "Cette route a été supprimée. Utilisez /v1/..."

## Migration pour les clients

### 1. Identifier les routes legacy

Vérifier les logs pour `legacy_route_access` :

```bash
grep "legacy_route_access" /var/log/astro/app.log
```

### 2. Mettre à jour les clients

Remplacer toutes les URLs :

- `/auth/` → `/v1/auth/`
- `/horoscope/` → `/v1/horoscope/`
- `/chat/` → `/v1/chat/`

### 3. Tester

Vérifier que les clients ne reçoivent plus de headers `Deprecation` ou `Sunset`.

### 4. Monitorer

Suivre la métrique `apigw_legacy_hits_total` pour confirmer la migration.

## Références

- [RFC 9745: The Deprecation HTTP Response Header Field](https://www.rfc-editor.org/rfc/rfc9745.html)
- [RFC 8594: The Sunset HTTP Header Field](https://www.rfc-editor.org/rfc/rfc8594.html)
- [RFC 8288: Web Linking](https://www.rfc-editor.org/rfc/rfc8288.html)
- [RFC 7231: HTTP/1.1 Semantics and Content](https://www.rfc-editor.org/rfc/rfc7231.html)
- [MDN: 308 Permanent Redirect](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/308)

## Dates clés

- **2025-10-24** : Dépréciation (début)
- **2025-12-31** : Sunset (fin du support)

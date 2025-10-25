# Politique de dépréciation API

## Vue d'ensemble

Cette politique définit les règles et processus pour la dépréciation des versions d'API et des endpoints dans notre plateforme.

## Versions d'API

### Version actuelle : `/v1`

- **Statut** : ✅ Actuelle et supportée
- **Début de support** : 2025-01-01
- **Fin de support prévue** : 2026-01-01 (12 mois de support)
- **Migration requise vers** : `/v2` (quand disponible)

### Versions dépréciées

#### `/v0` (Legacy)
- **Statut** : ⚠️ Dépréciée
- **Début de dépréciation** : 2025-01-01
- **Fin de support** : 2025-04-01
- **Action requise** : Migration vers `/v1` avant le 2025-04-01

## Processus de dépréciation

### 1. Avertissement de dépréciation (6 mois avant)
- Ajout d'un header `Deprecation: true` sur toutes les réponses
- Ajout d'un header `Sunset: YYYY-MM-DD` avec la date de fin de support
- Documentation mise à jour avec les alternatives recommandées
- Notification aux développeurs via changelog et email

### 2. Période de transition (3 mois avant)
- Les endpoints dépréciés continuent de fonctionner
- Headers d'avertissement maintenus
- Support clientiel limité aux questions de migration
- Documentation des alternatives renforcée

### 3. Fin de support
- Les endpoints dépréciés retournent `410 Gone`
- Redirection vers la documentation de migration
- Support clientiel uniquement pour les cas critiques

## Headers de dépréciation

### Headers retournés par l'API

```http
Deprecation: true
Sunset: 2025-04-01
Link: <https://api.example.com/docs/migration/v0-to-v1>; rel="deprecation"
```

### Exemple de réponse dépréciée

```json
{
  "code": "DEPRECATED_ENDPOINT",
  "message": "This endpoint is deprecated and will be removed on 2025-04-01. Please migrate to /v1/chat/answer",
  "trace_id": "abc123",
  "details": {
    "deprecated_since": "2025-01-01",
    "sunset_date": "2025-04-01",
    "migration_guide": "https://api.example.com/docs/migration/v0-to-v1"
  }
}
```

## Migration des endpoints

### `/v0/chat` → `/v1/chat`

#### Changements breaking
- Format de réponse modifié pour inclure `trace_id`
- Nouveaux codes d'erreur standardisés
- Support des `Idempotency-Key` requis pour les POST

#### Guide de migration

```javascript
// Ancien code (v0)
const response = await fetch('/v0/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token
  },
  body: JSON.stringify({
    message: 'Hello'
  })
});

// Nouveau code (v1)
const response = await fetch('/v1/chat/answer', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token,
    'Idempotency-Key': generateIdempotencyKey()
  },
  body: JSON.stringify({
    message: 'Hello'
  })
});
```

## Gestion des erreurs

### Codes d'erreur de dépréciation

- `DEPRECATED_ENDPOINT` : Endpoint déprécié mais encore fonctionnel
- `SUNSET_ENDPOINT` : Endpoint arrivé en fin de vie (410 Gone)

### Exemple d'erreur de fin de vie

```json
{
  "code": "SUNSET_ENDPOINT",
  "message": "This endpoint has been removed. Please use /v1/chat/answer instead.",
  "trace_id": "def456",
  "details": {
    "removed_since": "2025-04-01",
    "alternative_endpoint": "/v1/chat/answer",
    "migration_guide": "https://api.example.com/docs/migration/v0-to-v1"
  }
}
```

## Support et assistance

### Pendant la période de dépréciation
- Documentation complète de migration
- Exemples de code pour chaque endpoint
- Support clientiel prioritaire pour les questions de migration
- Webinaires et sessions de formation

### Après la fin de support
- Documentation archivée disponible
- Support clientiel limité aux cas critiques
- Pas de nouvelles fonctionnalités sur les versions dépréciées

## Calendrier des dépréciations

| Version | Début dépréciation | Fin de support | Statut |
|---------|-------------------|-----------------|---------|
| `/v0`   | 2025-01-01        | 2025-04-01      | ⚠️ Dépréciée |
| `/v1`   | -                 | 2026-01-01      | ✅ Actuelle |

## Contact

Pour toute question sur la migration ou la dépréciation :
- Email : api-support@example.com
- Documentation : https://api.example.com/docs
- Status page : https://status.example.com

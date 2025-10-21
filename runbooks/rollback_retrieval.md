# Rollback Drill — Bascule vecteur (FAISS ← cible)

Objectif: exécuter un exercice de rollback documenté pour revenir en mode FAISS-only en cas d’incident sur la cible.

## Pré-requis
- Accès au dépôt/ENV du service (fichier `.env` ou variables d’environnement gérées).
- Accès aux dashboards métriques (latence, erreurs, shadow, dual-write, outbox).
- Fenêtre de tir approuvée (staging puis prod si besoin).

## Étapes (ordre recommandé)
1. Mettre `FF_RETRIEVAL_DUAL_WRITE=OFF` (désactiver double écriture)
2. Purger le delta incohérent côté cible (si divergence détectée)
3. Mettre `FF_RETRIEVAL_SHADOW_READ=OFF` (désactiver lecture fantôme)
4. Forcer `RETRIEVAL_BACKEND=faiss` (FAISS-only)
5. Lancer des smoke tests API (chat/retrieval)
6. Vérifier SLO/latences (P50/P95), erreurs applicatives, alertes
7. Si OK, rouvrir progressivement shadow-read puis dual-write (piloté)

## Journal obligatoire (NDJSON)
Chaque drill doit produire une entrée NDJSON dans `artifacts/rollback_drill_log.ndjson`:

```
{
  "timestamp": "2025-10-21T14:50:00Z",
  "operator": "alice",
  "env_file": ".env.staging",
  "apply": false,
  "result": "success",
  "duration_s": 12.3,
  "changes": {
    "FF_RETRIEVAL_DUAL_WRITE": "OFF",
    "FF_RETRIEVAL_SHADOW_READ": "OFF",
    "RETRIEVAL_BACKEND": "faiss"
  },
  "notes": "dry-run staging"
}
```

## Commande (dry-run puis apply)
- Dry-run (pré-merge / staging):
```
python scripts/rollback_retrieval.py --env-file .env.staging --dry-run --operator alice --reason "drill"
```
- Application:
```
python scripts/rollback_retrieval.py --env-file .env.staging --apply --operator alice --reason "incident-123"
```

Le script crée une sauvegarde du fichier `.env` (suffixe `.bak`) en mode `--apply`, journalise l’opération, et n’insère aucune PII.

## Vérifications post-rollback
- Endpoints `/internal/retrieval/*` OK
- Latence primaire stable ; absence d’erreurs réseau cible
- `retrieval_dual_write_skipped_total{reason="circuit_open"}` stable/bas
- `retrieval_shadow_*` à zéro (si OFF)


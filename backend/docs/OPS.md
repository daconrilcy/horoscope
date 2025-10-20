"""
OPS Runbook — Retrieval Multi‑Tenant & RGPD

Ce document résume la configuration, l’exploitation et la purge RGPD pour le
stockage vectoriel multi‑tenant.
"""

from __future__ import annotations

# Variables d’environnement

- `VECSTORE_BACKEND` (faiss|memory) — backend vectoriel utilisé (défaut: faiss)
- `FAISS_DATA_DIR` — répertoire de persistance FAISS par tenant (défaut: `./var/faiss`)
- `TENANCY_MODE` — mode de tenancy (défaut: `simple`)
- `DEFAULT_TENANT` — tenant par défaut (défaut: `default`)
- `STORAGE_REGION` — région de stockage (documentation/flags; non contraignant dans ce dépôt)

# Sécurité du tenant

- Le tenant est dérivé via JWT/claims côté backend; n’utilisez un header `X‑Tenant`
  que s’il est injecté par un proxy d’auth de confiance (mTLS/signature).
- Validation/normalisation: regex `^[a-z0-9_-]{1,64}$` + lower/trim — valeurs invalides
  normalisées vers la valeur de fallback.

# Persistance FAISS

- Par tenant: `FAISS_DATA_DIR/<tenant>/index.faiss` + `docs.json`.
- Snapshots atomiques: écriture sur fichier temporaire, puis `os.replace`.
- Chargement paresseux: l’index/documents sont chargés au premier `search`.

# Purge RGPD (droit à l’oubli)

- Script: `python -m scripts.purge_tenant <tenant>`
- Audit JSONL: `artifacts/audit/tenant_purge.log` (créé si absent, rotation >10 MB).
- Format: `{ "ts": ISO8601Z, "tenant": str, "actor": str, "action": "purge", "backend": "faiss|memory", "status": "success|error", "error": str|null }`
- Actor: `PURGE_ACTOR` (env) > `getpass.getuser()` > `service`.
- Rétention: définissez une politique de rotation/copie vers un backend d’audit
  sécurisé selon vos contraintes (hors scope de ce dépôt).
- Autorisation: vérifiez le rôle (admin/compliance) côté endpoint/CLI avant d’appeler `purge_tenant`.

# Métriques

- `vecstore_index_total{tenant,backend}` — indexations
- `vecstore_search_total{tenant,backend}` — recherches
- `vecstore_purge_total{tenant,backend}` — purges
- `vecstore_op_latency_seconds{op,backend}` — latence par opération

# Conseils d’exploitation

- Cardinalité des labels: limitez le nombre de tenants en prod (whitelist),
  et surveillez les séries `{tenant,backend}`. Les valeurs invalides/hostiles
  sont normalisées vers un tenant par défaut.
- Sauvegardes: si vous persistez des index FAISS, snapshottez `FAISS_DATA_DIR`
  selon votre politique de sauvegarde. Faites‑le hors horaires de purge.
- Concurrence: si vous mutualisez les workers, ajoutez des verrous fichiers
  au besoin (flock) pour éviter les write races.


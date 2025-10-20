# Documentation

Ce dépôt regroupe la documentation dans le dossier `docs/`.

## Index

- Présentation du projet: `docs/PROJECT.md`
- Environnements et configuration (`.env`, `settings.py`): `docs/ENV-SETTINGS.md`

## Navigation rapide

- Projet → `docs/PROJECT.md`
- Environnements/Settings → `docs/ENV-SETTINGS.md`

## Dev local (sans Docker)

Pour exécuter en local avec des imports `backend.*` robustes, définissez `PYTHONPATH` vers le dossier `backend` avant d'exécuter vos commandes Python:

- Windows PowerShell:

```
$env:PYTHONPATH="backend"
```

- macOS/Linux:

```
export PYTHONPATH=backend
```

## Sécurité LLM — Guard I/O (Issue #9)

Variables d'environnement clés (voir `.env.example`):

- `LLM_GUARD_ENABLE` (`true|false`) — active/désactive les contrôles d'entrée/sortie.
- `LLM_GUARD_MAX_INPUT_LEN` (défaut `1000`) — longueur maximale autorisée pour la question.

Le guard applique:

- Sanitation d'entrée (trim, longueur max, denylist FR/EN contre prompt-injection).
- Masquage PII en sortie (emails → `[redacted-email]`, téléphones → `[redacted-phone]`).

## Secrets & Vault (Issue #10)

- Fallback: l’app résout d’abord via Vault (si `VAULT_ENABLED=true`), sinon via variables d’environnement, sinon via `settings.py`.
- Variables clés (voir `.env.example`): `VAULT_ENABLED`, `VAULT_ADDR`, `VAULT_TOKEN`.
- Pour les tests/dev, vous pouvez définir `VAULT_MOCK_OPENAI_API_KEY` (ne pas utiliser en prod).
- Rotation manuelle (audit uniquement, pas de valeur de secret en sortie):
  - `python -m backend.scripts.rotate_openai_key --key-id NEW_KEY_ID`

Artefacts d'audit:
- Les logs de rotation sont écrits dans `artifacts/secrets/rotation_*.log` et ne doivent pas être commités.

## Quotas & Budgets (Issue #11)

- QPS par tenant via middleware (`X-Tenant`), 429 si dépassement.
- Budgets LLM par tenant (avertissement à 80%, blocage doux à 100%).
- Variables env: `RATE_LIMIT_TENANT_QPS`, `TENANT_DEFAULT_BUDGET_USD`, `TENANT_BUDGETS_JSON` (JSON `{tenant: budget_usd}`).
- Métriques Prometheus:
  - `rate_limit_blocks_total{tenant,reason}`
  - `llm_cost_usd_total{tenant,model}`

## Celery Ops (Issue #12)

- Retries/backoff/timeouts configurés via `backend/app/celeryconfig.py`.
- Idempotence: utiliser la règle `task:{name}:{param_significatif}` via helper `make_idem_key(name, *parts)`.
- DLQ/Poison queue: `CELERY_MAX_FAILURES_BEFORE_DLQ` (env/settings) contrôle le seuil; les entrées DLQ stockent `{task, task_id, reason, ts}`.
- Métriques (Prom): `celery_task_retry_total{task}`, `celery_task_failure_total{task}`, `celery_dlq_total{queue}`.
Notes de sécurité et d'architecture:
- Confiance du header `X-Tenant`: ne pas faire confiance en prod sans mTLS/proxy d’auth; idéalement, dériver le tenant depuis un JWT/claim côté backend.
- Fenêtrage QPS: granularité à la seconde, store en mémoire (par instance). Pour un déploiement multi-instance, utiliser Redis (issue ultérieure).
- Exemptions: `/metrics` est ignoré par le rate-limit. `/health` peut être exempté via `RATE_LIMIT_EXEMPT_HEALTH=true`.

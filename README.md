[![PR Image Build (no push)](https://github.com/daconrilcy/horoscope/actions/workflows/pr_image_build.yml/badge.svg)](https://github.com/daconrilcy/horoscope/actions/workflows/pr_image_build.yml)

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

## Monitoring Worker (Issue #13)

- Endpoint /metrics côté worker via WSGI (port 9109):
  - `python -m backend.infra.monitoring.celery_metrics_server --port 9109`
  - Sécurité: par défaut, allowlist IP = `127.0.0.1,::1`. En prod, placez derrière un reverse-proxy (BasicAuth/mTLS) ou étendez l’allowlist via `--allowlist`.
- Queue depth (Redis): si `REDIS_URL` est défini, un poller optionnel met à jour `celery_queue_depth`. Noms de files via `CELERY_QUEUE_NAMES` (ex: `celery,default` ou JSON `["celery","default"]`).
- Procfile/compose (exemple minimal):
  - `worker: celery -A backend.app.celery_app.celery_app worker -l info`
  - `metrics: python -m backend.infra.monitoring.celery_metrics_server --port 9109`

### docker-compose

Services utiles (extraits):

```
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  worker:
    build: .
    command: celery -A backend.app.celery_app.celery_app worker -l info
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_QUEUE_NAMES=celery,default

  metrics:
    build: .
    command: python -m backend.infra.monitoring.celery_metrics_server --host 0.0.0.0 --port 9109 --allowlist "127.0.0.1,::1"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_QUEUE_NAMES=celery,default
    ports: ["9109:9109"]

  nginx-metrics:
    image: nginx:1.27-alpine
    depends_on: [metrics]
    ports: ["9110:9110"]
    volumes:
      - ./ops/nginx/metrics.conf:/etc/nginx/conf.d/metrics.conf:ro
      - ./ops/nginx/.htpasswd:/etc/nginx/.htpasswd:ro
```

Créer le user BasicAuth (exemple Linux/WSL):

```
mkdir -p ops/nginx
docker run --rm --entrypoint htpasswd httpd:2.4-alpine -nbB prometheus <MOT_DE_PASSE> > ops/nginx/.htpasswd
```

## Observability — Conseils (Issue #14)

- Token count: l’estimation par mots est un fallback. Si possible, utilisez le `token_usage` de l’API LLM; à défaut, `tiktoken` local avec le modèle connu pour une approximation stable.
- Source tenant: ne faites pas confiance au header `X-Tenant` côté frontal en prod. Préférez un `tenant_id` issu d’un JWT signé ou injecté par un reverse-proxy d’auth (mTLS), et utilisez-le comme label.
- Hit ratio multi‑workers: le gauge in‑process est indicatif. Pour un agrégat global robuste, utilisez les compteurs `retrieval_queries_total` et `retrieval_hits_total` et calculez le ratio en PromQL: `sum(retrieval_hits_total) / sum(retrieval_queries_total)` par `{backend,tenant}`.
- Cardinalité: limitez la variété des labels `tenant` et `model` (évitez des IDs à haute cardinalité) afin de préserver les performances du TSDB et du dashboard.

### Comptage de tokens (configurable)

- `TOKEN_COUNT_STRATEGY=auto|api|tiktoken|words` (défaut: `auto`).
- Ordre en `auto`: `api` (si usage renvoyé par le provider) → `tiktoken` (si dispo) → `words` (fallback).
- Installer l’extra tokens (optionnel) si vous voulez une estimation plus précise:
  - via pyproject: `pip install .[tokens]`
  - via fichier: `pip install -r requirements.tokens.txt`
  - Aucun secret n’est loggé; seul un compte est remonté en métriques.

## Release & Rollback (Issue #15)

- CI (GitHub Actions):
  - `.github/workflows/ci.yml`: gates PR — `ruff`, `compileall`, `pytest --cov>=90`, scans `gitleaks`, `trivy`.
  - `.github/workflows/release.yml`: build/push image vers GHCR + signature cosign (keyless, OIDC).
  - `.github/workflows/smoke.yml`: job manuel `workflow_dispatch` pour fumer une URL déployée.
- Release process (exemple):
  1. Merge en `main` → CI passe.
  2. Créer une release GitHub → image buildée/poussée/signée.
  3. Déployer en canary/blue‑green (hors scope repo), puis lancer `Smoke E2E` avec `base_url` canary.
  4. Si OK (<10 min), basculer le trafic.
- Rollback (concept):
  - Revenir au tag précédent du déploiement, ou redéployer l’image précédente depuis GHCR (signée), puis relancer `Smoke E2E`.
- Sécurité:
  - Pas de secrets exposés dans les logs workflows.
  - Cosign en keyless: nécessite `id-token: write` + policy d’admission côté cluster pour vérifier les signatures.
  - Admission policy (cluster): configurez une policy Sigstore/Cosign côté admission (OPA/Gatekeeper ou Kyverno) pour refuser les images non signées ou signées par une identité non autorisée.

Smoke E2E enrichi:
- Workflow `Smoke E2E` accepte un token (`api_token`) et exécute N appels `/chat/advise` en mesurant la latence; il échoue si la P95 dépasse `p95_ms` (défaut 2000 ms).

### PR Image Build (no push)
- Build Docker sur chaque PR (sans push) + scans Trivy (FS+image) + Gitleaks + Hadolint.
- Workflow: `.github/workflows/pr_image_build.yml`.
- Mode par défaut: `warn` (non bloquant). Passage en `strict` via `workflow_dispatch` (Actions → Run workflow → `trivy_mode=strict`).
- SBOM CycloneDX généré et uploadé comme artifact (optionnel si Trivy disponible sur runner).

Prometheus scrape (extrait):

```
scrape_configs:
  - job_name: "celery-worker-metrics"
    metrics_path: /metrics
    static_configs:
      - targets: ["localhost:9110"]
    basic_auth:
      username: "prometheus"
      password: "<MOT_DE_PASSE>"
```
Notes de sécurité et d'architecture:
- Confiance du header `X-Tenant`: ne pas faire confiance en prod sans mTLS/proxy d’auth; idéalement, dériver le tenant depuis un JWT/claim côté backend.
- Fenêtrage QPS: granularité à la seconde, store en mémoire (par instance). Pour un déploiement multi-instance, utiliser Redis (issue ultérieure).
- Exemptions: `/metrics` est ignoré par le rate-limit. `/health` peut être exempté via `RATE_LIMIT_EXEMPT_HEALTH=true`.

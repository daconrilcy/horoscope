# Runbook — Migration Retrieval (Shadow-read & Dual-write)

Objectif: migrer de FAISS vers un backend cible (weaviate/pinecone/elastic) en sécurité, via shadow-read et dual-write sous feature flags.

## Variables d'environnement

- `FF_RETRIEVAL_SHADOW_READ` — Active le shadow-read (défaut OFF)
- `FF_RETRIEVAL_SHADOW_SAMPLE_RATE` — Taux d'échantillonnage [0..1] (défaut 0.25)
- `RETRIEVAL_TENANT_ALLOWLIST` — Liste CSV des tenants autorisés (vide = tous)
- `RETRIEVAL_SHADOW_TIMEOUT_MS` — Timeout strict du shadow (défaut 800ms)
- `RETRIEVAL_TARGET_BACKEND` — Backend cible: `weaviate|pinecone|elastic`
- `FF_RETRIEVAL_DUAL_WRITE` — Active la double écriture (défaut OFF)
- `RETRIEVAL_DUAL_WRITE_CB_THRESHOLD` — Seuil du circuit breaker (défaut 3)
- `RETRIEVAL_DUAL_WRITE_CB_WINDOW_S` — Durée d'ouverture (défaut 30s)
- `RETRIEVAL_DUAL_WRITE_OUTBOX_MAX` — Taille max de l'outbox (défaut 1000)
- `RETRIEVAL_DUAL_WRITE_OUTBOX_TTL_S` — Âge max d'un item avant drop (défaut 86400s)

## Métriques à surveiller

- `retrieval_shadow_latency_seconds{backend,sample}` (Histogram)
- `retrieval_shadow_agreement_at_5{backend,k,sample}` (Histogram)
- `retrieval_shadow_ndcg_at_10{backend,k,sample}` (Histogram)
- `retrieval_shadow_dropped_total{reason}` (Counter: `queue_full|timeout`)
- `retrieval_dual_write_errors_total` (Counter)
- `retrieval_dual_write_skipped_total{reason="circuit_open"}` (Counter)
- `retrieval_dual_write_outbox_size` (Gauge)
- `retrieval_dual_write_outbox_dropped_total` (Counter)

## Procédure

1) Shadow-read — staging
- `FF_RETRIEVAL_SHADOW_READ=ON`, `FF_RETRIEVAL_SHADOW_SAMPLE_RATE=0.10`, `RETRIEVAL_TENANT_ALLOWLIST=<tenants internes>`
- Vérifier latence primaire stable; shadow latency raisonnable; drops faibles; histos de scores plausibles.

2) Shadow-read — canary prod (5–10%)
- Même flags que staging, allowlist très limitée.
- Surveiller 15–30 min. Élargir si RAS.

3) Dual-write (tenant pilote)
- `FF_RETRIEVAL_DUAL_WRITE=ON` pour un tenant pilote.
- Surveiller: erreurs, circuit_open skipped, outbox_size.

4) Replay outbox
- Inspection à blanc: `python scripts/replay_outbox.py --dry-run --max-items 100`
- Rejeu: `python scripts/replay_outbox.py --max-items 500 --sleep-ms 5`
- Intégration cron: toutes les 10 min (exit code 0 si OK).

5) Rollback rapide
- `FF_RETRIEVAL_DUAL_WRITE=OFF` → purge delta si nécessaire → `FF_RETRIEVAL_SHADOW_READ=OFF` → smoke tests → clôture incident.

## Logs & conformité

- Inclure `tenant` et `trace_id` dans les logs (pas de PII).
- Idempotency côté cible recommandée (clé: `(tenant, doc_id, content_hash)`).

## Plan d’activation progressive

Staging (pré/post‑merge de vérification)

- Env/flags:
  - `FF_RETRIEVAL_SHADOW_READ=ON`
  - `FF_RETRIEVAL_SHADOW_SAMPLE_RATE=0.10`
  - `RETRIEVAL_TENANT_ALLOWLIST=tenantA,tenantB`
  - `RETRIEVAL_SHADOW_TIMEOUT_MS=800`
- À surveiller (PromQL exemples):
  - P95 latence shadow:
    `histogram_quantile(0.95, sum(rate(retrieval_shadow_latency_seconds_bucket[5m])) by (le))`
  - Accord & nDCG (moyenne glissante):
    `sum(rate(retrieval_shadow_agreement_at_5_sum[5m])) / sum(rate(retrieval_shadow_agreement_at_5_count[5m]))`
    `sum(rate(retrieval_shadow_ndcg_at_10_sum[5m])) / sum(rate(retrieval_shadow_ndcg_at_10_count[5m]))`
  - Drops par raison:
    `sum(rate(retrieval_shadow_dropped_total[5m])) by (reason)`

Prod — canary (5–10 % trafic / allowlist restreinte)

- Même flags que staging, allowlist très limitée.
- Observation 15–30 min ; si stable → élargir allowlist et/ou `FF_RETRIEVAL_SHADOW_SAMPLE_RATE`.

Dual‑write (tenant pilote)

- `FF_RETRIEVAL_DUAL_WRITE=ON` sur 1 tenant.
- Surveiller:
  - `rate(retrieval_dual_write_errors_total[5m])`
  - `rate(retrieval_dual_write_skipped_total{reason="circuit_open"}[5m])`
  - `retrieval_dual_write_outbox_size`
- En cas de panne cible: breaker open (skips↑), rejouer via:
  `python scripts/replay_outbox.py --max-items 500`

Rollback instantané

- `FF_RETRIEVAL_DUAL_WRITE=OFF` → purge delta si besoin → `FF_RETRIEVAL_SHADOW_READ=OFF` → smoke tests → SLO OK.

## Règles d’alerting (exemples à adapter)

```
groups:
- name: retrieval-shadow
  rules:
  - alert: ShadowLatencyHighP95
    expr: histogram_quantile(0.95, sum(rate(retrieval_shadow_latency_seconds_bucket[5m])) by (le)) > 1.2
    for: 10m
    labels: { severity: warning }
    annotations:
      summary: "Shadow P95 latency > 1.2s (10m)"

  - alert: ShadowDropsSpike
    expr: sum(rate(retrieval_shadow_dropped_total[5m])) by (reason) > 5
    for: 10m
    labels: { severity: warning }
    annotations:
      summary: "Shadow drops > 5/5m"

- name: retrieval-dualwrite
  rules:
  - alert: DualWriteErrorsSpike
    expr: rate(retrieval_dual_write_errors_total[5m]) > 1
    for: 10m
    labels: { severity: warning }
    annotations:
      summary: "Dual-write errors > 1/5m"

  - alert: CircuitOpenSustained
    expr: rate(retrieval_dual_write_skipped_total{reason="circuit_open"}[5m]) > 0
    for: 15m
    labels: { severity: critical }
    annotations:
      summary: "Circuit breaker open (soutenu)"
```

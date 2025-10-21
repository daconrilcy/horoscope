# Phase 4.1 — Hardening & Evidence Pack (pré-Phase 5)

## Objectifs
1. **Sécurité**: LLM Guard *enforcement* (injection/PII), logs structurés, métriques.
2. **Observabilité/SLO**: SLOs chiffrés + dashboards + politiques d’error budget (burn-rate).
3. **Reliability**: Canary/blue-green **scriptés** + abort auto sur burn-rate; DR test (DB + vector store).
4. **Retrieval**: Dual-write & shadow-read *dans le proxy*; gates **agreement@5/nDCG@10**; journal 48h + rollback drill.
5. **API Governance**: `/v1`, enveloppe d’erreur, idempotency-keys, quotas/rate-limit **gateway**, metrics endpoint.
6. **Data Lifecycle**: PII masking logging/traces, TTL/rétentions, purge RGPD, catalogue PII.
7. **Evidence Pack**: artefacts exportés (coverage JSON, SLO report, bench, dashboards).

## Périmètre (exclus)
- **Monétisation/Entitlements** (Phase 5).

## Gates (acceptance criteria)
- **0 P0** ouverts; **0 P1** en retard sur retrieval/API/security/observabilité.
- `GET /chat/answer`: **P95 ≤ 300 ms**, **P99 ≤ 700 ms**, **err_rate ≤ 0,5%** @ QPS 50 / tenant.
- **Cutover**: `agreement@5 ≥ 95%` & `nDCG@10 ≥ 0,90` **pendant 48h** sous charge multi-tenant; **rollback drill** passé.
- **LLM Guard**: règles actives, tests d’attaque verts, métriques `llm_guard_block_total` visibles.
- **Gateway**: quotas/429 `Retry-After`, enveloppe d’erreur standard, idempotency-keys en place.
- **DR**: backup/restore testé (DB + vector store), RPO/RTO documentés.
- **Evidence Pack**: exports livrés et versionnés.

## Livrables
- Code (proxy, guard, gateway, CI/CD), **runbooks** (cutover, rollback, incident Sev1, purge RGPD), **dashboards** (SLO/burn), **rapports** (bench multi-tenant, slo_report, coverage JSON).

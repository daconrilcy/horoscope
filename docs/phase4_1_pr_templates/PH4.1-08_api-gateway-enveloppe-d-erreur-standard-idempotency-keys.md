<!-- PR template generated 2025-10-21 14:17 UTC -->
# [PH4.1-08] API Gateway: enveloppe d’erreur standard + idempotency-keys

Issue: **PH4.1-08** · Module: **apigw** · Type: **feature** · Sévérité: **P1** · Due: **2025-10-29**
Dependencies: — · Tags: api,contracts,idempotency
Branch: `feat/PH4.1-08-api-gateway-enveloppe-d-erreur-standard-idempotency-keys`

> **IMPORTANT** : Suivre **à la lettre** le guide [`phase4_1_agent_pr_implementation.mds`](phase4_1_agent_pr_implementation.mds) — **Ruff strict**, **mypy strict**, **interdit** `typing.List/Dict/Optional/Str` (utiliser `list`, `dict`, `str`, `X | None`), **coverage ≥ 90%** (packages touchés).

## Contexte
Uniformiser erreurs (`code`,`message`,`trace_id`), POST idempotent; tests e2e.

## Scope (STRICT)
- Implémenter **uniquement** le périmètre de **PH4.1-08** dans le module **apigw**.
- **Hors scope** : tout refactor transverse → créer une *refactor/chore issue* dédiée, la lier en dépendance.

## Implémentation (détails opérationnels)
- Normaliser **/v1**; enveloppe d'erreur `{code,message,trace_id}`.
- `Idempotency-Key` pour POST; retry-safe.
- Quotas/rate-limit au gateway par tenant; `429` + `Retry-After`.
- Timeouts/backoff cohérents; retry-budget par endpoint.
- Prom: `http_server_requests_seconds_bucket{route,method,status}`.

## Feature Flags
- Si applicable : désactivés par défaut (**OFF**) / allowlist tenant. Documenter: nom, défaut, activation/désactivation.

## Tests (à écrire)
- **Unitaires** : cas nominaux + erreurs.
- **Intégration/e2e** : seulement si nécessaire pour prouver le périmètre.
- Déterministes (seed fixe), pas d’IO réseau non mocké.
- **Coverage ≥ 90%** pour les packages touchés.

## CI Gates (bloquants)
- `make lint` (Ruff strict) ✅
- `make type` (mypy strict) ✅
- `make test` (pytest + coverage json) ✅
- `make slo` (fail on breach) ✅
- `scripts/check_no_typing_aliases.sh` (ban `typing.List/Dict/Optional/Str`) ✅

## Artefacts à joindre (si pertinents)
- `coverage.json` (extrait par package touché)
- SLO report (`slo_report.json`), bench report, cutover logs
- Captures/dashboards (JSON) utiles à la validation

## Risques & Rollback
1) Symptômes → dégradations SLO, erreurs runtime, alertes métriques  
2) Action → désactiver flags / **revert** la PR si nécessaire  
3) Vérification → happy path OK + SLO revenus à la normale

## Checklist finale
- [ ] Scope respecté, pas de hors-sujet
- [ ] Ruff + mypy **OK**
- [ ] **Aucun** `typing.List/Dict/Optional/Str`
- [ ] Coverage **≥ 90%** (packages touchés)
- [ ] Artefacts joints (si requis)
- [ ] PR ne référence **qu’une seule** issue

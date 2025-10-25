# PH4.1-10 — Suivi ops : buckets SLO, retries (métriques & règles), 410 headers, labels unifiés

## 🎯 Résumé
- **Buckets SLO-like** : http_server_requests_seconds_bucket = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 2.0].
- **Métriques retry** :
  - pigw_retry_attempts_total{route,result="allowed|blocked"}
  - pigw_retry_budget_exhausted_total{route}
- **Classification retry durcie** :
  - **Retry autorisés** : timeouts + 5xx transitoires (502/503), **bornés** par le budget.
  - **Pas de retry** : 4xx (400/401/403/409) et **429**.
- **410 Sunset** : Cache-Control: max-age=60, must-revalidate (aucun Retry-After).
  - **Option CDN** : Surrogate-Control: max-age=60 **uniquement** si APIGW_EDGE_SURROGATE=1|true|yes|on.
- **Labels de route unifiés** : usage central de 
ormalize_route (metrics HTTP, rate-limit, auth, store).

## ✅ Tests ajoutés
- **4xx/429** : zéro retry (aucun incrément …{result="allowed"}).
- **502/503** : retry **jusqu’au budget** + émission de …_budget_exhausted_total et …{result="blocked"} à l’épuisement.
- **500** : garde **single-increment** (pas de double comptage http_server_requests_total).
- **CDN gating** : Surrogate-Control présent **uniquement** si env activé.

## 🧪 Qualité
- Ruff/mypy strict ✅ — **types natifs uniquement** (aucun 	yping.List/Dict/Optional/Str).
- Couverture **apigw ≥ 90%** ✅.
- Buckets alignés SLO, **aucun risque de cardinalité**.

## 🚀 Rollout
- **Canary 10%** avec SLO Gate, surveillance 30–60 min :
  - histogram_quantile(0.95, sum(rate(http_server_requests_seconds_bucket[5m])) by (le,route))
  - sum(rate(apigw_retry_attempts_total{result="allowed"}[5m])) by (route)
  - sum(rate(apigw_retry_budget_exhausted_total[15m])) by (route)
- **Promotion 100%** si RAS.

## 📋 Checklist merge/rollout
- [ ] Lints/types/tests **verts** ; **coverage apigw ≥ 90%**.
- [ ] **SLO Gate** OK.
- [ ] Dashboards à jour : panels **Retry Allowed**, **Retry Budget**, **HTTP P95/P99**, **ratio 5xx**.
- [ ] Canary 10% : alerte si …_budget_exhausted_total soutenu ou P95 en hausse ; promotion si stable.

## 🔜 Follow-ups (petites PR dédiées)
- **E2E idempotent POST + retry** : vérifier retour **même status+body** via cache idempotent.
- **Property-based “cross-stack labels”** : un **seul** label oute pour /v1/chat/123?x=1&y=2 (metrics / RL / versioning).
- **Docs** docs/api/timeouts_retries.md : tableau par endpoint (timeouts, erreurs retryables, budget/jitter) + note CDN.

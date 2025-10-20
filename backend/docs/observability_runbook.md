# Runbook Observabilité

## Objectifs
- Visibilité latence & coûts par tenant/feature.
- Alertes budget 80%/100%.
- Traçabilité de bout en bout (OTEL).

## Tableaux Grafana (exemples)
- Latence Chat (P50/P95).
- Coûts LLM ($/jour, $/tenant).
- Hit-ratio retrieval & cache.
- Celery : queue depth, failures, runtime.

## Procédures
- Incident latence LLM : vérifier quota, fallback modèle, réduire contexte.
- Incident retrieval : vérifier index, bascule proxy, rollback si besoin.
- Incident Celery : analyse Flower, retry budget, poison queue.

## Budgets & Alertes
- Budgets LLM par tenant configurés via env: `TENANT_DEFAULT_BUDGET_USD`, `TENANT_BUDGETS_JSON`.
- Métriques de coût: `llm_cost_usd_total{tenant,model}`; calcul du coût MTD via `increase(llm_cost_usd_total[30d])`.
- Seuils SLO (voir `slo.yaml`): avertissement à 80%, blocage doux à 100%.
- Alertes Prometheus/Grafana: lier les règles d’alerte aux SLOs (latence P95, disponibilité, budget LLM).
- Runbook incident budget: réduire le périmètre (top-k, contexte), activer un modèle moins coûteux, limiter le QPS par tenant, notifier l’équipe.

## Liens utiles
- SLOs: `slo.yaml`, `backend/docs/slo.yaml`
- Dashboard Grafana: `backend/docs/grafana_dashboard.json`
- Rapport SLO mensuel: `python -m scripts.slo_report`

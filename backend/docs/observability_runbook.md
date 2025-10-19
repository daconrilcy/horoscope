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


# Tracing HTTP et corrélation (APIGW)

## Objectif
Décrire le modèle de confiance `X-Trace-ID`, linterop W3C Trace Context, et la corrélation logs ↔ métriques ↔ traces, ainsi que la propagation vers des workers.

## Modèle de confiance `X-Trace-ID`
- Production: `APIGW_TRACE_ID_TRUST_CLIENT = false` (par défaut).
- Comportement:
  - Si OFF: le gateway génère toujours un `trace_id` serveur (UUID v4) et, si présent, conserve la valeur client en `client_trace_id` (logs uniquement).
  - Si ON: le gateway accepte `X-Trace-ID` comme trace officiel (non recommandé en public).

## W3C Trace Context (optionnel)
- Lecture des headers `traceparent`/`tracestate` possible pour corréler avec OTel.
- Ne pas exposer ces valeurs dans des labels Prom; usage interne de corrélation uniquement.

## Corrélation
- Logs: JSON structurés avec `trace_id` et éventuellement `client_trace_id`.
- Métriques: pas de label haute cardinalité; `route/method/status` uniquement.
- Traces: exporter via OTLP si `OTLP_ENDPOINT` est configuré.

## Propagation vers workers
- Inclure `trace_id` dans les métadonnées des tâches (headers/task kwargs) pour relier HTTP → job.
- Le worker doit logger/corréler avec ce `trace_id`.

## Exclusions métriques
- Les endpoints `/metrics`, `/health`, `/docs`, `/openapi.json`, `/redoc` ne sont pas comptés dans les métriques HTTP pour ne pas biaiser P95/P99 et les taux derreur.

## Checklist dexploitation
- `APIGW_TRACE_ID_TRUST_CLIENT` OFF en prod.
- Dashboards: panels P95/P99 par route (histogram_quantile), ratio 5xx, top endpoints.
- SLO Gate avant promotion canary → production.

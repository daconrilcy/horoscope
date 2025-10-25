> Revue ops/qualité — PH4.1-13 (post-commit enqueue + idempotence worker)
>
> ✅ Validé fonctionnellement
>
> - Post-commit enqueue avec purge rollback/savepoints.
> - `@idempotent_task` : clé canonique robuste (JSON trié + normalisations), verrou Redis `SETNX` + TTL, états `in_progress/succeeded/failed`.
> - Métriques low-cardinality producer/worker ; Celery config durcie (acks late, reject on lost, prefetch=1, time_limit).
> - Tests : commit/rollback/savepoints, invariance de clé, concurrence simulée.
>
> 🛡️ Durcissements recommandés (faible effort, gros gain)
>
> 1. Transactional Outbox (optionnel) pour tâches critiques (réduire la fenêtre « commit→publish »).
> 2. Anti-zombie : récupération `in_progress` expirés (TTL + éventuellement heartbeat/reaper).
> 3. Atomicité lock→état (Lua/section critique) pour éviter états incohérents en cas de crash.
> 4. TTL/tailles bornées pour clés d’idempotence + dashboard « clés actives ».
> 5. Fail-open Redis documenté + métrique `worker_idempotency_store_errors_total{op}`.
> 6. Get-or-create artefact PDF (chemin déterministe par clé) pour éviter tout re-rendu.
> 7. Propagation `X-Idempotency-Key` API→worker (continuité end-to-end).
> 8. (Option) Histogramme de durée exécuté vs deduped.
>
> ✅ DoD
>
> - Ruff/mypy strict OK ; 463 tests verts ; aucun alias `typing.*`.
> - Métriques visibles dans `/metrics`, sans label `tenant`.
> - Runbook `docs/ops/idempotency.md` en place.

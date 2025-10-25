# Idempotency & Post-Commit Enqueue — Guide d'exploitation

Ce document décrit la stratégie d'idempotence côté workers et la publication post-commit
à l'API, ainsi que les métriques et la procédure de rattrapage.

## Philosophie

- Objectif réaliste: at-least-once + idempotence (exactly-once est non atteignable sans coûts).
- Émission de tâches uniquement après COMMIT de la transaction SQLAlchemy.
- Pour les tâches critiques, privilégier une Transactional Outbox.

## Publication post-commit (API→workers)

- Utilitaire: `backend/infra/ops/post_commit.py`
  - `enqueue_task_after_commit(session, task_name, *args, **kwargs)`
  - Enregistre un envoi à exécuter sur `after_commit`; purge sur `rollback`/savepoints.
- Métriques producer (low-cardinality):
  - `postcommit_enqueue_total{result="enqueued|rolled_back|skipped"}`
- Logs: JSON structuré `{task_name, trace_id?}` sans PII.

Recommandation: pour réduire la fenêtre «commit→publish», mettre en place une **Transactional
Outbox** (table `outbox` + dispatcher périodique). Le dispatcher réémet au redémarrage.

## Idempotence worker

- Utilitaire: `backend/infra/ops/idempotency.py`
  - `@idempotent_task(...)` applique la déduplication avant effets de bord.
  - Verrou via Redis `SETNX` + TTL; suivi d'état: `in_progress → succeeded|failed`.
  - Clé canonique: voir ci-dessous.
- Métriques worker (low-cardinality):
  - `worker_idempotency_attempts_total{task,result="allowed|deduped"}`
  - `worker_idempotency_state_total{task,state="in_progress|succeeded|failed"}`
- Logs: `{task_name, idempotency_key, trace_id?}` (pas d'email/tel/token).

### Clé canonique (recommandée)

Construite depuis `(task_name, args, kwargs)` normalisés, puis encodés en JSON trié
(`sort_keys=True`, `separators=(',', ':')`). Normalisations supportées:

- `bytes|bytearray` → base64
- `set|frozenset` → liste triée
- `datetime` → ISO UTC (timezone imposée)
- `dict|list|tuple` → récursif; chute en `str(value)` si non sérialisable

Exposition: `canonical_task_key(task_name, args, kwargs)`.

## Celery — réglages de robustesse

Dans `backend/app/celeryconfig.py`:

- `task_acks_late = True`
- `task_reject_on_worker_lost = True`
- `worker_prefetch_multiplier = 1`
- `task_time_limit = 300`

Appliquer l'idempotence avant tout effet de bord (I/O, writes, external calls).

## Runbook de rattrapage (sans Transactional Outbox)

1) Extraire les demandes métier et les artefacts attendus (ex. PDF existants).
2) Croiser avec `postcommit_enqueue_total{result="enqueued"}` sur la fenêtre d'incident.
3) Rejouer les manquants via un script ad hoc (batch d'enqueues).
4) Vérifier absence de doublons côté worker (métrique `deduped`).

Avec Transactional Outbox (recommandé):

1) Scanner la table `outbox` pour les messages non délivrés.
2) Redéclencher le dispatcher; vérifier vidage de la file (`row_count=0`).

## Tests d'exploitation (à automatiser)

- Savepoints/transactions imbriquées: 0 émission si rollback partiel; 1 émission au commit final.
- Concurrence: double submit même clé → une seule exécution, 1 `deduped`.
- Clé canonique: invariance à l'ordre des dicts/kwargs; sets triés; bytes→base64.
- Crash simulé entre commit et publish: avec outbox, rattrapage automatique.

## FAQ

- « Peut-on atteindre exactly-once ? » — Non sur systèmes distribués sans store coordonné; viser
  at-least-once + idempotence (verrou + clé canonique + états).



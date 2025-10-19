# Migration Retrieval — FAISS -> DB vectorielle

## Stratégie
- **Dual-write**: indexer dans FAISS **et** cible.
- **Shadow-read**: comparer résultats en lecture, sans impacter l’utilisateur.
- **Agreement@k**: viser >= 0.9 avant bascule.
- **Feature flag**: bascule progressive par pourcentage de trafic.
- **Rollback**: < 10 minutes, scripté.

## Opérations
- **Backup/restore** index cible (RTO <= 30 min, RPO <= 15 min).
- **Warmup**: pré-chargement index (temps & RAM documentés).
- **Capacité**: QPS cible, P95, taille index, coûts.

## Validation
- Batteries de tests e2e + smoke tests post-déploiement.


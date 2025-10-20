## Résumé
- _Pourquoi_ / _Quoi_ :
- **Issue liée** : Closes #

## Type
- [ ] feat    [ ] fix    [ ] docs    [ ] chore    [ ] refactor    [ ] test

## Checklist DoD (must-have)
- [ ] **Tests**: unit/integration ajoutés ou adaptés (compte rendu ✅  /  ❌)
- [ ] **CI verte**: ruff + pytest + workflows OK
- [ ] **SLOs**: impact analysé ; alertes mises à jour si nécessaire (slo.yaml)
- [ ] **Budget LLM**: métriques exposées / pas d’impact / MAJ requise
- [ ] **Observabilité**: métriques/logs/labels conformes (cardinalité maîtrisée)
- [ ] **Tenancy/RGPD**: `tenant_from_context()` utilisé ; `safe_tenant()` partout ; purge/audit si applicable
- [ ] **Sécurité**: secrets non commités ; en-têtes/claims validés ; droits purge contrôlés
- [ ] **Docs**: README / runbooks / RAPPORT_PHASE4 mis à jour (+ liens artefacts CI)
- [ ] **Rollback**: plan de retour documenté ou _not applicable_
- [ ] **Artefacts**: captures/lien Grafana/artefacts CI inclus ci-dessous

## Observabilité / Liens utiles
- Dashboard Grafana : <!-- GRAFANA_DASHBOARD_URL si dispo -->
- Artefacts CI (bench/embeddings/SLO report) : `artifacts/bench`, `artifacts/embeddings`, `artifacts/slo`

## Risques & mitigations
- Principaux risques :
- Mitigations / plan de surveillance post-merge :

## Post-merge
- [ ] Vérifier alertes/burn-rate 24–48h
- [ ] Lancer rapport SLO mensuel si besoin

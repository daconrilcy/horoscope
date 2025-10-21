<!-- PR template generated 2025-10-21 14:17 UTC -->
# [PH4.1-01] RetrievalProxy: intégrer dual-write & shadow-read (feature-flags)

Issue: **PH4.1-01** · Module: **retrieval** · Type: **feature** · Sévérité: **P0** · Due: **2025-10-26**
Dependencies: — · Tags: retrieval,cutover,proxy,flags
Branch: `feat/PH4.1-01-retrievalproxy-int-grer-dual-write-shadow-read-feature-flags`

> **IMPORTANT** : Suivre **à la lettre** le guide [`phase4_1_agent_pr_implementation.mds`](phase4_1_agent_pr_implementation.mds) — **Ruff strict**, **mypy strict**, **interdit** `typing.List/Dict/Optional/Str` (utiliser `list`, `dict`, `str`, `X | None`), **coverage ≥ 90%** (packages touchés).

## Contexte
Implémenter dans `retrieval_proxy` la double écriture (FAISS+cible) et la lecture fantôme; flags ON/OFF; tests intégration.

## Scope (STRICT)
- Implémenter **uniquement** le périmètre de **PH4.1-01** dans le module **retrieval**.
- **Hors scope** : tout refactor transverse → créer une *refactor/chore issue* dédiée, la lier en dépendance.

## Implémentation (détails opérationnels)
- Implémenter **dans le proxy** (pas via scripts seuls) :
  - `FF_RETRIEVAL_DUAL_WRITE` (OFF par défaut) pour ingestion sur primaire + cible.
  - `FF_RETRIEVAL_SHADOW_READ` (OFF par défaut) pour lecture parallèle sans impacter la réponse.
  - Exposer métriques: `retrieval_dual_write_errors_total`, `retrieval_shadow_agreement_at_5`, `retrieval_shadow_ndcg_at_10`.
- Respecter les seuils dans les tests (latence plafonnée/contrôlée).

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

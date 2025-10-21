<!-- PR template generated 2025-10-21 14:17 UTC -->
# [PH4.1-05] Deploy strategy: canary/blue-green scriptée + abort sur burn-rate

Issue: **PH4.1-05** · Module: **cicd** · Type: **feature** · Sévérité: **P0** · Due: **2025-10-26**
Dependencies: — · Tags: deploy,canary,bluegreen,error-budget
Branch: `feat/PH4.1-05-deploy-strategy-canary-blue-green-script-e-abort-sur-burn-rate`

> **IMPORTANT** : Suivre **à la lettre** le guide [`phase4_1_agent_pr_implementation.mds`](phase4_1_agent_pr_implementation.mds) — **Ruff strict**, **mypy strict**, **interdit** `typing.List/Dict/Optional/Str` (utiliser `list`, `dict`, `str`, `X | None`), **coverage ≥ 90%** (packages touchés).

## Contexte
Jobs CI/CD pour canary; conditions d’abort (SLO burn-rate); rollback auto; docs runbook.

## Scope (STRICT)
- Implémenter **uniquement** le périmètre de **PH4.1-05** dans le module **cicd**.
- **Hors scope** : tout refactor transverse → créer une *refactor/chore issue* dédiée, la lier en dépendance.

## Implémentation (détails opérationnels)
- Ajouter workflows GitHub Actions ciblés (PR Quality/Canary/Embeddings).
- Bloquer PR si conditions non remplies (ruff/mypy/coverage/SLO, ban typing alias).

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

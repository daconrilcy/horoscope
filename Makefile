# ============================================================
# Makefile — Qualité & Vérifications
# Objet : centraliser les commandes de lint, format, tests.
# ============================================================

.PHONY: lint test type typecheck verify slo

lint:
	@ruff check backend --fix && ruff format backend

test:
	@pytest -q

typecheck:
	# Mypy en mode informatif (pas d'échec bloquant ici)
	@mypy backend || true

type: typecheck

verify:
	@python -m compileall -q backend && make lint && make test

slo:
	@python -m scripts.slo_report --output-dir artifacts/slo --json-out artifacts/slo/slo_report.json $${SLO_METRICS_JSON:+--metrics $${SLO_METRICS_JSON}} $${SLO_FAIL_ON_BREACH:+--fail-on-breach}


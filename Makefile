# ============================================================
# Makefile — Qualité & Vérifications
# Objet : centraliser les commandes de lint, format, tests.
# ============================================================

.PHONY: lint test typecheck verify

lint:
	@ruff check backend --fix && ruff format backend

test:
	@pytest -q

typecheck:
	# Mypy en mode informatif (pas d'échec bloquant ici)
	@mypy backend || true

verify:
	@python -m compileall -q backend && make lint && make test


# Tests Backend

Ce dossier contient les tests d’intégration/basiques du backend FastAPI.

## Comment exécuter
- Pré-requis: dépendances installées (`requirements.txt`).
- Sous Windows (PowerShell):
  - `Set-Location` à la racine du repo, puis:
  - ``$env:PYTHONPATH='backend'; pytest -q``
- Sous macOS/Linux:
  - ``PYTHONPATH=backend pytest -q``

Notes:
- `PYTHONPATH=backend` permet d’importer les modules comme `from app.main import app`.
- Les tests utilisent `fastapi.testclient.TestClient` (sync) pour simplifier.

## Suites et cas couverts
- `backend/tests/test_health.py`
  - Vérifie que `GET /health` renvoie 200 et `{\"status\": \"ok\"}`.
- `backend/tests/test_charts.py`
  - Effectue un flux complet: `POST /charts/compute` avec un payload valide,
    puis `GET /charts/{id}` et vérifie la cohérence de l’identifiant.

## Ajouter de nouveaux tests
- Nommer les fichiers `test_*.py` et les fonctions `test_*`.
- Placer les tests dans ce dossier ou des sous-dossiers.
- Utiliser `TestClient(app)` pour tester les endpoints HTTP.
- Garder les tests indépendants: pas d’état partagé entre tests.

## Commandes utiles
- Lancer tous les tests: `pytest -q`
- Lancer un test précis: `pytest -q backend/tests/test_charts.py::test_compute_and_get_chart`
- Verbose: `pytest -v`

## Bonnes pratiques
- Préférer des assertions explicites et messages clairs.
- Documenter brièvement le but de chaque test (docstring en tête de fichier).

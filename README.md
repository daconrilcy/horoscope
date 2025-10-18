# Documentation

Ce dépôt regroupe la documentation dans le dossier `docs/`.

## Index

- Présentation du projet: `docs/PROJECT.md`
- Environnements et configuration (`.env`, `settings.py`): `docs/ENV-SETTINGS.md`

## Navigation rapide

- Projet → `docs/PROJECT.md`
- Environnements/Settings → `docs/ENV-SETTINGS.md`

## Dev local (sans Docker)

Pour exécuter en local avec des imports `backend.*` robustes, définissez `PYTHONPATH` vers le dossier `backend` avant d'exécuter vos commandes Python:

- Windows PowerShell:

```
$env:PYTHONPATH="backend"
```

- macOS/Linux:

```
export PYTHONPATH=backend
```

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

## Sécurité LLM — Guard I/O (Issue #9)

Variables d'environnement clés (voir `.env.example`):

- `LLM_GUARD_ENABLE` (`true|false`) — active/désactive les contrôles d'entrée/sortie.
- `LLM_GUARD_MAX_INPUT_LEN` (défaut `1000`) — longueur maximale autorisée pour la question.

Le guard applique:

- Sanitation d'entrée (trim, longueur max, denylist FR/EN contre prompt-injection).
- Masquage PII en sortie (emails → `[redacted-email]`, téléphones → `[redacted-phone]`).

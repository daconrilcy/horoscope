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

## Secrets & Vault (Issue #10)

- Fallback: l’app résout d’abord via Vault (si `VAULT_ENABLED=true`), sinon via variables d’environnement, sinon via `settings.py`.
- Variables clés (voir `.env.example`): `VAULT_ENABLED`, `VAULT_ADDR`, `VAULT_TOKEN`.
- Pour les tests/dev, vous pouvez définir `VAULT_MOCK_OPENAI_API_KEY` (ne pas utiliser en prod).
- Rotation manuelle (audit uniquement, pas de valeur de secret en sortie):
  - `python -m backend.scripts.rotate_openai_key --key-id NEW_KEY_ID`

Artefacts d’audit:
- Les logs de rotation sont écrits dans `artifacts/secrets/rotation_*.log` et ne doivent pas être commités.

# Variables d'environnement et `settings.py`

Ce projet utilise Pydantic Settings pour charger la configuration depuis les variables d'environnement et des fichiers `.env`.

## Principe de chargement

Ordre de priorité des valeurs (de la plus forte à la plus faible):
- Variables d'environnement du processus (ex: `APP_ENV`, `DATABASE_URL`, etc.).
- Fichier `.env` sélectionné dynamiquement (voir ci‑dessous).

Le module `backend/core/settings.py` sélectionne le fichier `.env` selon la logique suivante:
1. Si `ENV_FILE` est défini → utiliser ce chemin explicitement.
2. Sinon, si un fichier `.env.{APP_ENV}` existe → l'utiliser (ex: `.env.prod`).
3. Sinon → fallback sur `.env`.

Encodage du fichier `.env` : UTF‑8.

## Variables principales

- `APP_NAME` (str) : nom de l'application.
- `APP_ENV` (str) : environnement courant (`dev`, `prod`, etc.).
- `APP_DEBUG` (bool) : active le mode debug.
- `APP_HOST` (str) : hôte d'écoute (`0.0.0.0` par défaut).
- `APP_PORT` (int) : port d'écoute (8000 par défaut).
- `CORS_ORIGINS` (list[str] ou list[URL]) : origines autorisées.
- `DATABASE_URL` (str) : URL de connexion base de données.
- `REDIS_URL` (str) : URL de connexion Redis.

Remarque : les variables d'environnement réelles ont toujours priorité sur le contenu du fichier `.env`.

## Exemples de `.env`

`.env` (développement)
```
APP_ENV=dev
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/app
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

`.env.prod` (production)
```
APP_ENV=prod
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000
DATABASE_URL=postgresql+psycopg://user:pass@db:5432/app
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=["https://app.example.com"]
```

## Forcer un fichier `.env` spécifique

Définir la variable d'environnement `ENV_FILE` avec un chemin absolu ou relatif :

- PowerShell
```
$env:ENV_FILE = ".env.ci"; uvicorn backend.app.main:app --reload
```

- Bash
```
ENV_FILE=.env.ci uvicorn backend.app.main:app --reload
```

## Utilisation dans le code

```
from backend.core.settings import get_settings

settings = get_settings()
print(settings.APP_ENV, settings.DATABASE_URL)
```

`get_settings()` construit une instance de configuration en appliquant les priorités ci-dessus.

## Flags de migration Retrieval (Phase 4.1)

Ces variables contrôlent la migration du backend de recherche (dual-write & shadow-read).

- `FF_RETRIEVAL_DUAL_WRITE` (ou `RETRIEVAL_DUAL_WRITE`) — active la double écriture vers la cible (défaut: OFF)
- `FF_RETRIEVAL_SHADOW_READ` (ou `RETRIEVAL_SHADOW_READ`) — active la lecture fantôme sans impacter la réponse (défaut: OFF)
- `RETRIEVAL_TARGET_BACKEND` — backend cible: `weaviate` | `pinecone` | `elastic` (défaut: `weaviate`)

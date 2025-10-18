"""Conteneur minimal de dépendances.

Objectif du module
------------------
- Fournir un point unique pour accéder aux dépendances globales (ex: settings).
- Évolutif vers un conteneur d'injection de dépendances si nécessaire.
"""

from core.settings import get_settings


class Container:
    """Expose les dépendances construites à l'initialisation de l'app."""

    def __init__(self):
        # Configuration applicative chargée depuis l'environnement et .env
        self.settings = get_settings()


container = Container()

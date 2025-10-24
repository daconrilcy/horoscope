"""Dépôt de contenus basé sur fichiers JSON.

Ce module implémente un dépôt de contenus simple utilisant des fichiers JSON pour stocker et
récupérer des extraits de texte par identifiant.
"""

import json
import os


class JSONContentRepository:
    """Dépôt de contenus basé sur un fichier JSON.

    Chaque extrait (snippet) est indexé par un identifiant unique et contient typiquement des
    fragments de texte utilisés par l'API.
    """

    def __init__(self, path: str):
        """Initialise le dépôt et garantit l'existence du fichier.

        Paramètres:
        - path: chemin du fichier JSON contenant les extraits.
        """
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def get_snippet(self, snippet_id: str) -> dict:
        """Retourne un extrait par identifiant.

        Si l'identifiant est absent, renvoie un placeholder minimal.
        """
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get(snippet_id, {"id": snippet_id, "text": "(content missing)"})

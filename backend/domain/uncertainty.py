"""Calcul du score de précision basé sur la certitude temporelle.

Ce module fournit des fonctions pour calculer des scores de précision basés sur la qualité des
informations temporelles disponibles.
"""

from backend.domain.entities import TimeCertainty


def precision_score(time_certainty: TimeCertainty) -> int:
    """Calculate a precision score based on temporal certainty.

    Args:
        time_certainty: Niveau de certitude de l'heure de naissance.

    Returns:
        int: Score de précision de 1 à 5.
    """
    mapping = {
        "exact": 5,
        "morning": 3,
        "afternoon": 3,
        "evening": 3,
        "unknown": 1,
    }
    return mapping.get(time_certainty, 1)

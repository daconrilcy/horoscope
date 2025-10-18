"""Dépendances partagées pour les routes de l'API.

But du module
-------------
- Centraliser la création des instances nécessaires aux endpoints (services,
  dépôts, clients externes, etc.).
- Offrir un point d’ancrage pour brancher un vrai conteneur d’injection de
  dépendances plus tard, sans modifier les routes.

Comportement actuel
-------------------
- `InMemoryChartRepo` conserve les cartes en mémoire (adapté aux démos/tests).
- `ChartService` expose la logique de calcul d’une carte (mock pour l’instant).
"""

from domain.services import ChartService
from infra.repositories import InMemoryChartRepo

# Instances simples; pourront être remplacées par un conteneur DI ultérieurement
chart_repo = InMemoryChartRepo()
chart_service = ChartService()

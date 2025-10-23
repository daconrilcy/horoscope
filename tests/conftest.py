"""
Configuration de test pour pytest avec gestion des chemins.

Ce module configure pytest pour résoudre les imports backend en ajoutant la racine du projet au
sys.path pour les tests.
"""

import os
import sys

# Ensure project root is on sys.path so that
# imports like `from backend...` resolve.
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

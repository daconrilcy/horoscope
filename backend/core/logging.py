"""Configuration de logging basée sur structlog.

Objectif du module
------------------
- Fournir une configuration de logs structurés lisibles en développement.
"""

import logging
import sys

import structlog


def setup_logging():
    """Configure structlog pour produire des logs détaillés et filtrables."""
    timestamper = structlog.processors.TimeStamper(fmt="ISO")
    structlog.configure(
        processors=[
            timestamper,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

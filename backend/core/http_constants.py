"""Constantes HTTP pour éviter les valeurs magiques dans le code.

Ce module définit les codes de statut HTTP les plus couramment utilisés dans l'application pour
améliorer la lisibilité et éviter les valeurs magiques.
"""

# Codes de statut HTTP courants
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_TOO_MANY_REQUESTS = 429
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_BAD_GATEWAY = 502

# Limites et seuils courants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 50
DEFAULT_RATE_LIMIT = 100

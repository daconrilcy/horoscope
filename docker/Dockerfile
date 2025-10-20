# syntax=docker/dockerfile:1
# Objectif: image pour exécuter l'API FastAPI avec Python + deps.
FROM python:3.12-slim
# --------------------------------------------------------------------
# STAGE: base — dépendances min, sans libs lourdes (torch, etc.)
# --------------------------------------------------------------------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# OS deps minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml requirements*.txt ./
# Installer le strict minimum commun pour CI (léger) avec pip versionnée (DL3013)
ARG PIP_VERSION=25.2
RUN pip install --no-cache-dir --upgrade "pip==${PIP_VERSION}" \
 && if [ -f requirements.ci.txt ]; then pip install --no-cache-dir -r requirements.ci.txt ; fi

# --------------------------------------------------------------------
# STAGE: ci — build PR léger (sans extras lourds)
# Installe uniquement ce qu’il faut pour linters/tests unitaires.
# --------------------------------------------------------------------
FROM base AS ci
COPY backend ./backend
COPY tests ./tests
COPY pytest.ini ./
RUN python -m compileall -q backend \
 && python -c "import sys; print('Python OK:', sys.version)"
CMD ["python", "-c", "print('ci image ready')"]

# --------------------------------------------------------------------
# STAGE: prod — image finale complète (utilisée par release.yml)
# Garder l’installation complète, y compris extras nécessaires.
# --------------------------------------------------------------------
FROM python:3.12-slim AS prod
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# OS deps runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml requirements*.txt ./
ARG PIP_VERSION=25.2
RUN pip install --no-cache-dir --upgrade "pip==${PIP_VERSION}" \
 && if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt ; fi

COPY backend ./backend
EXPOSE 8000
CMD ["python", "-m", "backend.app.main"]
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

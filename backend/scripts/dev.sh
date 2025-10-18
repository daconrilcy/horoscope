#!/usr/bin/env bash
# Objectif du fichier: Décrire l'objectif de dev.sh
# TODO: compléter cette description.

set -euo pipefail

# Resolve repository root (works from any cwd)
THIS_FILE="${BASH_SOURCE[0]}"
SCRIPT_DIR="$(cd "$(dirname "${THIS_FILE}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

# Auto-activate virtualenv if present
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  elif [[ -f .venv/Scripts/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/Scripts/activate
  fi
fi

# Load .env if present (export all keys)
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source ./.env
  set +a
fi

# Ensure backend is on PYTHONPATH
if [[ -z "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${REPO_ROOT}/backend"
else
  case ":${PYTHONPATH}:" in
    *:"${REPO_ROOT}/backend":*) ;; # already present
    *) export PYTHONPATH="${REPO_ROOT}/backend:${PYTHONPATH}" ;;
  esac
fi

# Defaults (overridable)
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

# Prefer uvicorn CLI; fallback to python -m
if command -v uvicorn >/dev/null 2>&1; then
  UVICORN_CMD=(uvicorn)
else
  UVICORN_CMD=(python -m uvicorn)
fi

exec "${UVICORN_CMD[@]}" app.main:app --host "${HOST}" --port "${PORT}" --reload "$@"

#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-promote}"  # promote|abort

case "$ACTION" in
  promote)
    echo "[deploy] promoting canary to 100%..."
    # TODO: replace with actual rollout command
    echo "(pretend) rollout to 100%"
    ;;
  abort)
    echo "[deploy] aborting canary and rolling back..."
    # TODO: replace with actual rollback command
    echo "(pretend) rollback to previous version"
    ;;
  *)
    echo "usage: $0 [promote|abort]" >&2
    exit 2
    ;;
esac

exit 0


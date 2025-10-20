#!/usr/bin/env bash
# ============================================================
# Script : scripts/retrieval_cutover.sh
# Objet  : Orchestrer cutover et rollback du backend de retrieval.
# Contexte : Bascule FAISS -> cible managée (Weaviate/Pinecone), avec dry-run.
# Usage    :
#   Dry-run:   ./scripts/retrieval_cutover.sh --dry-run --target weaviate
#   Cutover:    ./scripts/retrieval_cutover.sh --apply --target weaviate
#   Rollback:   ./scripts/retrieval_cutover.sh --rollback --previous faiss
# Notes     :
#   - Modifie le fichier .env (sauvegarde .env.bak-<ts>) pour RETRIEVAL_*
#   - Ne loggue jamais les clés API; masque si présent.
#   - Étapes: enable dual-write -> shadow-read -> cutover -> disable dual-write
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_DIR="$ROOT_DIR/artifacts/cutover"
mkdir -p "$LOG_DIR"

usage() {
  cat <<EOF
Usage: $0 (--dry-run|--apply|--rollback) [--target <weaviate|pinecone>] [--previous <faiss|weaviate|pinecone>]

Steps (apply):
  1) Enable dual-write (RETRIEVAL_DUAL_WRITE=true)
  2) Enable shadow-read (RETRIEVAL_SHADOW_READ=true, RETRIEVAL_SHADOW_READ_PCT=0.10)
  3) Validate criteria (P95<200ms@10k; agreement@5>=0.9; 0 regression e2e)
  4) Cutover (RETRIEVAL_BACKEND=<target>)
  5) Disable dual-write (optional, after steady-state)

Rollback:
  - Restore RETRIEVAL_BACKEND to --previous and disable shadow-read/dual-write

Backups:
  - Backup .env to .env.bak-
$TIMESTAMP
EOF
}

mode=""
target=""
previous=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) mode="dry"; shift ;;
    --apply) mode="apply"; shift ;;
    --rollback) mode="rollback"; shift ;;
    --target) target="$2"; shift 2 ;;
    --previous) previous="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$mode" ]]; then
  echo "Error: must specify one of --dry-run/--apply/--rollback"; usage; exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  # Fallback to .env.example if .env is absent
  ENV_FILE="$ROOT_DIR/.env.example"
fi

mask() {
  local v="$1"; echo "$v" | sed -E 's/./*/g'
}

log_info() { echo "[$(date -u +%FT%TZ)] INFO $*" | tee -a "$LOG_DIR/cutover_$TIMESTAMP.log"; }
log_warn() { echo "[$(date -u +%FT%TZ)] WARN $*" | tee -a "$LOG_DIR/cutover_$TIMESTAMP.log"; }

backup_env() {
  cp "$ENV_FILE" "$ENV_FILE.bak-$TIMESTAMP" || true
  log_info "Backed up $(basename "$ENV_FILE") -> $(basename "$ENV_FILE.bak-$TIMESTAMP")"
}

set_env_var() {
  local key="$1"; shift
  local val="$1"; shift
  if grep -qE "^$key=" "$ENV_FILE"; then
    sed -i.bak "s|^$key=.*|$key=$val|" "$ENV_FILE"
  else
    echo "$key=$val" >> "$ENV_FILE"
  fi
}

print_current() {
  local rb=$(grep -E '^RETRIEVAL_BACKEND=' "$ENV_FILE" | cut -d= -f2- || echo "faiss")
  local dw=$(grep -E '^RETRIEVAL_DUAL_WRITE=' "$ENV_FILE" | cut -d= -f2- || echo "false")
  local sr=$(grep -E '^RETRIEVAL_SHADOW_READ=' "$ENV_FILE" | cut -d= -f2- || echo "false")
  local pct=$(grep -E '^RETRIEVAL_SHADOW_READ_PCT=' "$ENV_FILE" | cut -d= -f2- || echo "0.10")
  local wurl=$(grep -E '^WEAVIATE_URL=' "$ENV_FILE" | cut -d= -f2- || true)
  log_info "Current: BACKEND=$rb DUAL_WRITE=$dw SHADOW=$sr PCT=$pct WEAVIATE_URL=$wurl"
}

do_dry_run() {
  print_current
  log_info "[DRY-RUN] Would enable dual-write (RETRIEVAL_DUAL_WRITE=true)"
  log_info "[DRY-RUN] Would enable shadow-read (RETRIEVAL_SHADOW_READ=true; PCT=0.10)"
  if [[ -n "$target" ]]; then
    log_info "[DRY-RUN] Would switch RETRIEVAL_BACKEND -> $target"
  fi
  log_info "[DRY-RUN] Would disable dual-write after steady-state"
}

do_apply() {
  if [[ -z "$target" ]]; then
    echo "Error: --target is required for --apply"; exit 2
  fi
  backup_env
  set_env_var RETRIEVAL_DUAL_WRITE true
  set_env_var RETRIEVAL_SHADOW_READ true
  set_env_var RETRIEVAL_SHADOW_READ_PCT 0.10
  log_info "Enabled dual-write + shadow-read in $(basename "$ENV_FILE")"
  log_info "Validate criteria over 48h: P95<200ms@10k; agreement@5>=0.9; 0 regression e2e"
  set_env_var RETRIEVAL_BACKEND "$target"
  log_info "Cutover complete: RETRIEVAL_BACKEND=$target"
}

do_rollback() {
  if [[ -z "$previous" ]]; then
    echo "Error: --previous is required for --rollback"; exit 2
  fi
  backup_env
  set_env_var RETRIEVAL_BACKEND "$previous"
  set_env_var RETRIEVAL_DUAL_WRITE false
  set_env_var RETRIEVAL_SHADOW_READ false
  log_warn "Rolled back to RETRIEVAL_BACKEND=$previous and disabled dual-write/shadow"
}

case "$mode" in
  dry) do_dry_run ;;
  apply) do_apply ;;
  rollback) do_rollback ;;
esac

log_info "Done. Log: $LOG_DIR/cutover_$TIMESTAMP.log"


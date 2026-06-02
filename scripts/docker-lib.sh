#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$REPO_ROOT/backups/docker"
CONTAINER_DB_PATH="/root/.booruswipe/booruswipe.db"
HEALTH_URL="http://localhost:8000/health"

compose() {
  (cd "$REPO_ROOT" && docker compose "$@")
}

ensure_backup_dir() {
  mkdir -p "$BACKUP_DIR"
}

timestamp() {
  date +%Y%m%d-%H%M%S
}

latest_backup() {
  shopt -s nullglob
  local backups=("$BACKUP_DIR"/booruswipe-db-*.sqlite)
  shopt -u nullglob

  if ((${#backups[@]} == 0)); then
    return 1
  fi

  printf '%s\n' "${backups[@]}" | sort | tail -n 1
}

backup_db_to() {
  local destination="$1"
  compose run --rm --no-deps -T booruswipe sh -lc "test -f '$CONTAINER_DB_PATH' && cat '$CONTAINER_DB_PATH'" > "$destination"
}

restore_db_from() {
  local source="$1"
  local staged_db="$CONTAINER_DB_PATH.restore.$$"

  compose down
  compose run --rm --no-deps -T booruswipe sh -lc "cat > '$staged_db' && mv '$staged_db' '$CONTAINER_DB_PATH'" < "$source"
  compose up -d
}

swap_db_with() {
  local source="$1"
  local live_backup

  live_backup="$(mktemp "$BACKUP_DIR/booruswipe-db-live-$(timestamp)-XXXXXX.sqlite")"

  if ! backup_db_to "$live_backup"; then
    rm -f "$live_backup"
    return 1
  fi

  if ! restore_db_from "$source"; then
    rm -f "$live_backup"
    return 1
  fi

  if ! mv "$live_backup" "$source"; then
    rm -f "$live_backup"
    return 1
  fi
}

wait_for_health() {
  local timeout_seconds="${1:-60}"
  local deadline=$((SECONDS + timeout_seconds))

  until curl -fsS "$HEALTH_URL" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      return 1
    fi
    sleep 2
  done
}

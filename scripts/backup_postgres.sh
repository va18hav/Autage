#!/usr/bin/env bash
# Create a compressed PostgreSQL backup from the Compose database container.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_SERVICE="${DB_SERVICE:-db}"
DB_USER="${DB_USER:-autage}"
DB_NAME="${DB_NAME:-autage}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "${BACKUP_DIR}"
OUTPUT="${BACKUP_DIR}/autage-${TIMESTAMP}.dump"
PARTIAL="${OUTPUT}.partial"

cleanup() {
    rm -f "${PARTIAL}"
}
trap cleanup EXIT

printf 'Backing up database "%s" to %s...\n' "${DB_NAME}" "${OUTPUT}"

docker compose exec -T "${DB_SERVICE}" pg_dump \
    --username="${DB_USER}" \
    --dbname="${DB_NAME}" \
    --format=custom \
    --no-owner \
    > "${PARTIAL}"

mv "${PARTIAL}" "${OUTPUT}"
chmod 600 "${OUTPUT}"
trap - EXIT

printf 'Backup complete: %s (%s)\n' "${OUTPUT}" "$(du -h "${OUTPUT}" | cut -f1)"
printf 'Verify it with: docker compose exec -T %s pg_restore --list < %s\n' "${DB_SERVICE}" "${OUTPUT}"

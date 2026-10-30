# PostgreSQL backup and restore

This application stores incidents, runbooks, users, and encrypted integration
credentials in PostgreSQL. Back up the database before upgrades, migrations, or
risky changes.

## Create a backup

From the repository root:

```bash
bash scripts/backup_postgres.sh
```

The script writes a custom-format dump to `./backups/autage-<UTC timestamp>.dump`
and restricts the file to the current user.

Useful overrides:

```bash
BACKUP_DIR=/secure/autage bash scripts/backup_postgres.sh
DB_NAME=autage DB_USER=autage bash scripts/backup_postgres.sh
```

Verify the dump contains a table of contents:

```bash
docker compose exec -T db pg_restore --list < backups/autage-2026-10-30T120000Z.dump
```

## Restore a backup

This is destructive: it replaces the current database. Stop writers first.

```bash
docker compose stop api worker

# Recreate an empty database, forcing existing connections closed.
docker compose exec -T db dropdb --if-exists --force -U autage autage
docker compose exec -T db createdb -U autage -O autage autage

# Restore the custom-format dump.
docker compose exec -T db pg_restore --no-owner -U autage -d autage \
  < backups/autage-2026-10-30T120000Z.dump

docker compose start api worker
curl -fsS http://localhost:8000/health
```

The final health check should return Postgres and Redis as `ok`.

## Important notes

- Backups contain encrypted integration credentials. Keep the dump files private.
- `AUTAGE_SECRET_KEY` must remain the same, otherwise encrypted credentials in the
  restored database cannot be decrypted.
- Test a restore on a disposable copy before relying on a backup during a real
  incident.

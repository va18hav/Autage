# Autage v1.0 Hardening Checklist

**Scope:** self-hosted, single-admin, read-only SRE copilot for a small trusted group.
This is an MVP checklist, not a multi-tenant production-SaaS checklist.

Tick an item only when it is actually working in the deployment.

---

## Must do before sharing v1.0

### Deployment and access

- [x] Serve the dashboard and API over HTTPS; set `COOKIE_SECURE=true`.
- [ ] Stop publishing Postgres `5432` and Redis `6379`; keep them on a private
  Docker network.
- [ ] Set `CORS_ORIGINS` to the real dashboard origin instead of localhost defaults.
- [ ] Keep `.env` out of git, readable only by the owner (`chmod 600`), with unique
  production secrets.
- [ ] Add basic proxy security headers: HSTS, `X-Content-Type-Options`,
  `X-Frame-Options`/`frame-ancestors`, and `Referrer-Policy`.

### Reliability

- [x] Make `/health` verify Postgres and Redis, not just return `{"status":"ok"}`.
- [x] Use PostgreSQL as the incident queue with `FOR UPDATE SKIP LOCKED`; remove the
  separate Redis job enqueue.
- [x] Add a worker timeout and limited retries; mark the incident `FAILED` after the
  final attempt.
- [x] Resume interrupted `TRIAGING` incidents from LangGraph checkpoints after a
  worker restart.
- [x] Add one simple PostgreSQL backup command and document the restore procedure.

### Product safety

- [x] Require at least 12 characters for passwords and document the bcrypt cost.
- [x] Verify the Kubernetes ServiceAccount has only `get`/`list`/`watch`; it must not
  read Secrets, exec into pods, or write resources.
- [ ] Run backend tests plus dashboard lint/build before each release, preferably in CI.

---

## Deferred until after v1.0

These are worthwhile later, but not blockers for a small first group of users:

- JWT logout/password-change invalidation and refresh-token rotation.
- Full audit logging and retention/PII-redaction automation.
- Metrics, tracing, error tracking, and alerting.
- Multi-tenancy, HA, load testing, and formal SLOs.
- Redis TLS/password, separate migration DB roles, and dedicated migration jobs.
- Container non-root hardening, image scanning, and dependency-audit CI gates.
- Advanced SSRF controls beyond the current trusted admin configuration.

---

## Already in place

- Required `AUTAGE_SECRET_KEY`, `JWT_SECRET_KEY`, and `DB_PASSWORD`; no insecure
  fallbacks.
- Setup-token-protected registration and password reset.
- Login/setup rate limiting, generic login failures, and bcrypt timing equalisation.
- CSRF double-submit protection for authenticated writes.
- 24-hour JWT sessions.
- HMAC-signed webhooks with a DB-configured secret.
- PostgreSQL-backed incident queue with bounded retries and stale-lease recovery.
- LangGraph Postgres checkpoints for resuming interrupted agent runs.
- Read-only Kubernetes tool catalog, TLS verification, and fail-closed credentials.
- Single-user database constraint.
- Automated backend tests and dashboard lint/build.

---

## Suggested next three steps

1. **Queue failure handling + worker recovery** — prevents silently stuck incidents.
2. **HTTPS, private DB/Redis ports, and secure cookies** — required before exposing it
   outside your machine.
3. **Health checks and database backup/restore** — enough operational safety for a
   small user group.

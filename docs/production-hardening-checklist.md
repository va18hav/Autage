# Autage Production Hardening Checklist

Created: 2026-10-29
Scope: self-hosted, single-tenant, read-only v1 (`crash_loop` and `bad_deployment` only)

Use this as the working list for the hardening session. Tick an item only when its
acceptance criterion is met. File references point at the current implementation.

---

## P0 — Blockers before any real user or production cluster

### 1. Secrets and configuration

- [ ] Remove insecure defaults from `services/config.py`:
  - `DB_PASSWORD = "autage_password"`
  - `WEBHOOK_SECRET = "autage-webhook-secret"`
  - `DB_USER = "autage"` / `DB_NAME = "autage"` defaults
  - `COOKIE_SECURE = False`
- [ ] Make `AUTAGE_SECRET_KEY` required and validate its length/format at startup.
- [ ] Make `JWT_SECRET_KEY` independent and required; never fall back to `WEBHOOK_SECRET`.
- [ ] Remove the `WEBHOOK_SECRET` environment fallback in
  `services/http/routes/webhook.py`; require the DB-configured secret.
- [ ] Rotate the Fernet key currently used for credential encryption and re-encrypt
  credentials (or wipe and re-enter them).
- [ ] Move all secrets out of `docker-compose.yml` into Docker secrets, a secret
  manager, or a root-owned `.env` with `0600` permissions.
- [ ] Add startup validation that fails fast with one clear message listing every
  missing/invalid setting.
- [ ] Remove copied development values from `.env.example`; use placeholders plus
  generation commands.

**Done when:** a fresh deployment with no explicit secrets exits non-zero and logs
exactly what must be provided.

### 2. Network and transport

- [ ] Serve the dashboard and API over HTTPS only, behind Caddy, Traefik, or nginx.
- [ ] Set `COOKIE_SECURE=true` and verify `Secure`, `HttpOnly`, and `SameSite` on the
  session cookie.
- [ ] Add HSTS, `X-Content-Type-Options`, `X-Frame-Options` / CSP `frame-ancestors`,
  `Referrer-Policy`, and a dashboard Content-Security-Policy.
- [ ] Restrict `CORS_ORIGINS` to the real dashboard origin. Reject wildcards when
  credentials are enabled.
- [ ] Do not publish Postgres (`5432`) or Redis (`6379`) ports. Keep them on a private
  Docker network only.
- [ ] Put Redis behind a password and TLS; do not expose it to the host.
- [ ] Add allowed-host enforcement (`TrustedHostMiddleware` or proxy equivalent).
- [ ] Add request body-size limits and request timeouts for API and webhook routes.

**Done when:** external scans see only the HTTPS dashboard/API ports, and cookies are
rejected over plain HTTP.

### 3. Authentication and authorization

- [ ] Protect first-user registration with a one-time setup token or a CLI-only
  initialization command. Prevent two concurrent first registrations.
- [ ] Add login rate limiting, lockout/backoff, and generic failure responses.
- [ ] Add CSRF protection for cookie-authenticated state-changing routes
  (settings, runbook delete, incident delete, logout).
- [ ] Shorten JWT lifetime and add rotation/invalidation on password change or logout.
- [ ] Enforce a password policy and a deliberate bcrypt cost.
- [ ] Add audit events for login success/failure, credential changes, settings changes,
  runbook deletion, and incident deletion.
- [ ] Consider `SameSite=Strict` when dashboard and API share a site.

**Done when:** an unauthenticated or CSRF-forged request cannot change settings or
delete data, and brute-force attempts are throttled.

### 4. Webhook safety

- [ ] Require a webhook secret; remove the environment fallback.
- [ ] Add a timestamp header with a tolerance window and a replay cache.
- [ ] Add per-source IP/rate limiting.
- [ ] Enforce a maximum body size and require a JSON object payload.
- [ ] Make incident creation and queue enqueue atomic. Current flow commits the
  incident, then enqueues; an enqueue failure leaves a permanent `PENDING` row.
- [ ] Add a unique constraint or explicit dedupe window for fingerprints.
- [ ] Surface queue-enqueue failures to the caller and mark the incident failed or
  schedule a retry.

**Done when:** replayed, oversized, unsigned, or queue-failed webhooks cannot create
silent stuck incidents.

### 5. Worker reliability

- [ ] Configure per-job timeout, retries, backoff, and a failure/dead-letter state.
- [ ] Make `run_agent_task` idempotent: re-running must not duplicate steps or
  overwrite a completed diagnosis inconsistently.
- [ ] Add a startup sweeper that recovers `PENDING` incidents left after a restart.
- [ ] Ensure every failure path marks the incident `FAILED` and publishes
  `incident_failed` exactly once.
- [ ] Limit worker concurrency and add graceful shutdown/restart behavior.
- [ ] Configure ARQ health checks and Redis reconnect behavior.
- [ ] Avoid unbounded `asyncio.to_thread` pressure during evidence collection.

**Done when:** killing the worker mid-job leaves a visible failed/retryable incident,
never a permanently stuck one.

### 6. Kubernetes safety

- [ ] Document and verify a read-only Role/ClusterRole:
  `get`, `list`, `watch` only; no `secrets`, `exec`, `port-forward`, or writes.
- [ ] Run `kubectl auth can-i --list` with the production ServiceAccount and store
  the result in the deployment record.
- [ ] Add namespace allowlist/denylist if the deployment must be scoped.
- [ ] Keep the existing fail-closed credential handling and TLS verification.
- [ ] Keep the existing token-in-kubeconfig approach; never pass tokens in argv.
- [ ] Add audit logging for every evidence read: incident, tool, target, timestamp.
- [ ] Do not add restart/rollback/scale actions in v1. If added later, require explicit
  human approval and a full audit trail.

**Done when:** the ServiceAccount cannot read Secrets, exec into pods, or mutate any
resource, and this is proven by a permission check.

### 7. Database and migrations

- [ ] Stop running `alembic upgrade head` on every API container start. Use one
  dedicated migration job before rolling out API replicas.
- [ ] Back up the database before every migration and test the restore procedure.
- [ ] Add migration tests from an empty database and from the previous release.
- [ ] Set connection-pool limits, connect timeouts, and statement timeouts.
- [ ] Use separate database roles for runtime and migrations.
- [ ] Require a strong database password and TLS.
- [ ] Document that destructive migrations need an explicit backup and rollback plan.

**Done when:** an API restart never mutates the schema, and a failed migration can be
restored from a tested backup.

### 8. Data protection and retention

- [ ] Decide retention for incidents, raw alerts, execution traces, and logs
  (for example: incidents 90 days, traces 30 days).
- [ ] Implement scheduled deletion and document it.
- [ ] Redact secrets and likely PII from raw alerts, logs, prompts, and stored traces.
- [ ] Encrypt database backups and restrict access to them.
- [ ] Add an export/delete path for a single incident.
- [ ] Document what is sent to external LLM providers and whether that is acceptable.

**Done when:** an operator can state exactly where data lives, how long it is kept,
and how to delete it.

---

## P1 — Required before normal production traffic

### 9. Observability

- [ ] Structured JSON logs with request/job IDs, incident ID, and no secrets.
- [ ] Readiness and liveness endpoints that check Postgres and Redis, not just
  `{"status": "ok"}`.
- [ ] Metrics for webhook requests, queue depth, job duration, failures, LLM latency,
  and Kubernetes evidence failures.
- [ ] Error tracking with alerting.
- [ ] Alerts for stuck `PENDING` incidents, repeated worker failures, and database
  connection exhaustion.
- [ ] Dashboard/API latency and 5xx monitoring.

### 10. Container and host hardening

- [ ] Run API, worker, and dashboard as non-root users.
- [ ] Read-only root filesystem, `no-new-privileges`, and dropped Linux capabilities.
- [ ] CPU/memory limits and requests for every service.
- [ ] Pin image digests and scan images for vulnerabilities in CI.
- [ ] Keep the dashboard build static and served by a minimal web server.
- [ ] Add log rotation and disk-space alerts.
- [ ] Run containers with a restrictive network policy where supported.

### 11. Application security

- [ ] Add rate limits to auth, webhook, settings, and LLM-backed endpoints.
- [ ] Validate and restrict provider `base_url` values to prevent SSRF.
- [ ] Validate the Kubernetes API URL against SSRF/private-network policy.
- [ ] Sanitize/escape all rendered LLM and alert content in the dashboard.
- [ ] Add CSP and other security headers to the dashboard build.
- [ ] Review dependencies with `pip-audit` / `npm audit` and add a CI gate.
- [ ] Add an explicit vulnerability disclosure/security policy.

### 12. Testing and CI

- [ ] Add integration tests against real Postgres and Redis containers, not only the
  in-memory fake.
- [ ] Add security tests for unsigned/replayed webhooks, CSRF, rate limits, and
  unauthorized access.
- [ ] Add migration upgrade/downgrade tests.
- [ ] Add a container smoke test for API, worker, dashboard, and database.
- [ ] Run lint, type checks, unit tests, and dependency audits on every change.
- [ ] Add a pre-release checklist with backup, migrate, deploy, and smoke-test steps.

---

## P2 — Operational maturity

- [ ] Define SLOs for webhook acceptance, triage completion, and diagnosis latency.
- [ ] Add load testing for webhook bursts and worker concurrency.
- [ ] Test Redis/Postgres outages and worker crashes.
- [ ] Automate encrypted backups with retention and restore drills.
- [ ] Write rotation runbooks for Fernet, JWT, webhook, database, and Kubernetes
  credentials.
- [ ] Automate dependency and base-image updates.
- [ ] Add a migration dry-run in CI for every release.
- [ ] Write operator runbooks for deploy, rollback, backup, restore, and incident
  investigation.
- [ ] Add a "known limitations" page for the read-only v1.

---

## Baseline already in place

These should be preserved while hardening:

- [x] Fixed evidence playbooks; the LLM does not choose tools.
- [x] Read-only Kubernetes tool catalog.
- [x] Fail-closed Kubernetes credentials and mandatory TLS verification.
- [x] Kubernetes token kept in a private temporary kubeconfig, not argv.
- [x] Bounded kubectl output, log tails, runbook sections, and prompt evidence.
- [x] HMAC verification for webhooks.
- [x] Cookie-based auth protecting incidents, runbooks, and settings routes.
- [x] Structured diagnosis persisted in `incidents.analysis`.
- [x] Migrations for incident type/analysis and LLM step-key cleanup.

---

## Current known gaps (evidence from this repository)

| Area | Current state | File |
| --- | --- | --- |
| Default secrets | DB password, webhook secret, and non-secure cookie defaults exist | `services/config.py` |
| JWT fallback | JWT can fall back to the webhook secret | `services/http/auth.py` |
| Registration | First user is created by any caller while the user table is empty | `services/http/routes/auth.py` |
| CSRF | No CSRF protection for cookie-authenticated writes | `services/http/app.py` |
| Rate limits | None on login, webhook, or settings | `services/http/routes/` |
| CORS | Localhost defaults; no production validation | `services/config.py` |
| Compose secrets | Credentials are hardcoded and DB/Redis ports are published | `docker-compose.yml` |
| Migrations | API container runs migrations on every start | `Dockerfile` |
| Queue atomicity | Incident commit and ARQ enqueue are separate operations | `services/http/routes/webhook.py` |
| Worker retries | No per-job timeout, retry, backoff, or dead-letter setup | `services/worker/main.py` |
| Health checks | `/health` does not check Postgres or Redis | `services/http/app.py` |
| Audit logs | No audit trail for auth, settings, evidence reads, or deletes | throughout |
| Retention | No retention or scheduled deletion for incidents/traces | throughout |
| Observability | No metrics, tracing, or structured request logging | throughout |

---

## Suggested first five changes

1. Remove all insecure defaults and make secrets required at startup.
2. Stop publishing Postgres/Redis and hardcode-free the Compose deployment.
3. Add setup-token registration, login rate limiting, and CSRF protection.
4. Make webhook incident creation + enqueue atomic and add replay protection.
5. Add worker timeouts/retries plus a `PENDING`-incident recovery sweeper.

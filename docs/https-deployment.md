# HTTPS deployment

Caddy is the single public entrypoint. It terminates HTTPS and proxies:

```text
https://<AUTAGE_HOST>/       -> dashboard:80
https://<AUTAGE_HOST>/api/*  -> api:8000
```

The dashboard and API are not published directly. The API is bound to host
loopback only for local debugging.

## Local Compose

```bash
docker compose up -d --build
```

Open `https://localhost`.

Caddy uses its own local certificate authority for `localhost`, so the first
visit may show a certificate warning. To trust it on macOS:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-local-ca.crt
security add-trusted-cert -d -r trustRoot \
  -k ~/Library/Keychains/login.keychain-db ./caddy-local-ca.crt
rm ./caddy-local-ca.crt
```

Restart the browser after trusting the CA.

## Public VM with a DNS name

1. Point an `A`/`AAAA` record at the VM.
2. Allow inbound TCP `80` and `443` in the firewall.
3. Set `AUTAGE_HOST` in `.env`:

```bash
AUTAGE_HOST=autage.example.com
```

4. Start the stack:

```bash
docker compose up -d --build
```

Caddy obtains and renews the public certificate automatically. `COOKIE_SECURE`
is already forced on by Compose.

## Private network or VM IP

Use the internal-CA Caddyfile:

```bash
CADDYFILE=./deploy/Caddyfile.internal \
AUTAGE_HOST=autage.internal \
docker compose up -d --build caddy api dashboard
```

This encrypts traffic, but clients must trust the internal CA. This is suitable
for a VPN or trusted internal network, not the public internet.

## Kubernetes

Use the cluster's existing Ingress or Gateway API instead of the Caddy container.
Set:

- `COOKIE_SECURE=true`
- CORS to the dashboard origin, if the API is on a separate origin
- `/api/*` routed to the API and `/` routed to the dashboard

## Verify

```bash
curl -I https://localhost
curl -fsS https://localhost/api/health
```

In the browser, the auth and CSRF cookies should show `Secure`.

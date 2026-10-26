# Testing Autage against a real Kubernetes cluster (kind)

A plain-English guide. No Kubernetes knowledge assumed.

## What all these words mean

| Word | Meaning |
|---|---|
| **Cluster** | A set of machines (real or simulated) that run your apps and keep them alive. Autage diagnoses problems in such clusters. |
| **Pod** | One running app instance inside the cluster. It can crash, get killed, restart. |
| **kubectl** | The CLI "remote control" for a cluster. |
| **kind** | "Kubernetes in Docker" — a **real** Kubernetes cluster running inside a Docker container on your own machine. Free, disposable, made for testing. |
| **ServiceAccount (SA)** | A cluster "login" you can hand to apps — like a bot account. Here, a read-only one for Autage. |
| **Token** | The password for that bot account. A single long line starting with `eyJ` (a JWT). Paste it into Settings → Kubernetes. |

## Why this exists

Autage diagnoses clusters by running real kubectl commands against them, so it needs
a cluster it can connect to. `kind` gives you a genuine one in ~1 minute, free and
disposable: a real `auth-service` pod that OOMKills and crash-loops forever (our
"sick patient"), plus a read-only bot account for the agent.

## One-time setup (one command)

```bash
bash scripts/setup_kind_cluster.sh
```

This:
1. Checks/installs `kind` + `kubectl` via Homebrew.
2. Creates a cluster named `autage`.
3. Creates namespace `production` and deploys `auth-service` — a pod deliberately
   configured to OOMKill and crash-loop forever (our "sick patient").
4. Creates a read-only bot account (`autage-ro`, `view` role) and prints:
   - the **Server URL** (`https://host.docker.internal:<port>`)
   - a **Token** valid for one year
   - the **CA certificate** (PEM block)

## Connecting Autage (2 manual steps, one time)

1. If you started Autage before creating the cluster, restart it so the
   containers pick up the fresh kube network:
   ```bash
   docker compose up -d api worker
   ```
2. Dashboard → **Settings → Kubernetes**:
   - **Server URL:** `https://host.docker.internal:<port>` — *NOT* `127.0.0.1`.
     Reason: Autage itself runs inside Docker containers; from inside a container,
     `127.0.0.1` means "the container itself", not your Mac. Docker provides the
     special name `host.docker.internal` that always means "the Mac".
   - **Token:** paste the whole printed line.
   - **Cluster CA certificate:** paste the whole printed PEM block
     (`-----BEGIN CERTIFICATE-----` … `-----END CERTIFICATE-----`).
   - All three fields are required: Autage TLS-verifies the connection against
     this certificate (the same check as `curl --cacert`) — it proves the
     server you are handing your token to is genuinely YOUR cluster. There is
     no skip-verification option. Click **Test connection** — expect
     *"TLS-verified… read access confirmed"*.

## Fire a real incident

```bash
uv run python scripts/send_mock_alert.py --live
```

- `--live` looks up a **real pod name from the cluster** (picking the most
  crash-looping one), so the alert references a pod that actually exists and the
  agent can read its logs directly. Without the flag, the script invents a
  plausible-but-nonexistent name (still fine — the agent self-corrects, it's
  just a harder test).

Open the incident in the dashboard and watch: the agent plans real kubectl
commands, reads the real crash logs of `auth-service-…` in `production`, and
diagnoses from genuine OOMKill evidence.

Cross-check manually:
```bash
kubectl get pods -n production
kubectl logs -n production deploy/auth-service --previous
```

## Useful commands

| Action | Command |
|---|---|
| See the victims | `kubectl get pods -n production -w` |
| Reprint URL + token | `bash scripts/setup_kind_cluster.sh --token` |
| Wipe the cluster entirely | `bash scripts/setup_kind_cluster.sh --destroy` |
| Everything again from scratch | `--destroy`, then the setup command |

## Troubleshooting

- **`The connection to the server localhost:8080 was refused`** (when using
  kubectl yourself) — no cluster exists yet, or the cluster was created but you
  deleted `~/.kube/config`. Run the setup script.
- **Cluster verification failed (HTTP 401)** — the token was mangled during
  copy-paste. Reprint it with `--token` and paste the whole line, no quotes.
- **Could not reach cluster (URLError) after entering `127.0.0.1...`** — expected
  when Autage runs in Docker. Use the `host.docker.internal` URL from the script.
- **Token expired** (after ~1 year) — `bash scripts/setup_kind_cluster.sh --token`
  prints a fresh one; re-save it in Settings.

## Notes

- The token is strictly read-only (`view` ClusterRole) — Autage cannot delete or
  modify anything in the cluster.
- Nothing leaves your machine: the cluster lives in Docker; the token is valid
  only for that local cluster.
- CI keeps the offline unit-test suite (no cluster needed); this setup is what
  exercises the real pipeline.

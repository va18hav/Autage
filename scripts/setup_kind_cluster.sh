#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Autage — local real-cluster test environment (kind + broken app + RO token)
#
# Creates a disposable, REAL Kubernetes cluster (inside Docker) with a
# deliberately crashing pod, plus a read-only ServiceAccount token that
# Autage can use from Settings → Kubernetes.
#
# Usage:
#   bash scripts/setup_kind_cluster.sh            # create / (re)apply
#   bash scripts/setup_kind_cluster.sh --destroy  # delete everything
#   bash scripts/setup_kind_cluster.sh --token    # (re)print credentials only
#
# Everything lives inside Docker on this machine. Nothing touches the cloud.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

CLUSTER_NAME="autage"
NAMESPACE="production"
SA_NAME="autage-ro"
DEPLOYMENT="auth-service"
TOKEN_DURATION="8760h"   # 1 year

info()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31mxx>\033[0m %s\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# ── prerequisites ────────────────────────────────────────────────────────────
have docker || fail "Docker is not installed. Install Docker Desktop first: https://www.docker.com/products/docker-desktop/"
docker info >/dev/null 2>&1 || fail "Docker is installed but not running. Start Docker Desktop and retry."
have kind     || { warn "kind not found — installing via Homebrew…"; brew install kind; }
have kubectl  || { warn "kubectl not found — installing via Homebrew…"; brew install kubectl; }

# ── destroy mode ─────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--destroy" ]]; then
    info "Deleting kind cluster '${CLUSTER_NAME}'…"
    kind delete cluster --name "${CLUSTER_NAME}" 2>/dev/null || true
    info "Done. The cluster (and everything in it) is gone; Autage's app containers were untouched."
    exit 0
fi

# ── cluster ──────────────────────────────────────────────────────────────────
if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
    warn "Cluster '${CLUSTER_NAME}' already exists — reusing it."
else
    info "Creating kind cluster '${CLUSTER_NAME}' (~1 minute)…"
    kind create cluster --name "${CLUSTER_NAME}"
fi

# ── read-only identity ───────────────────────────────────────────────────────
info "Creating read-only ServiceAccount '${SA_NAME}'..."
kubectl get serviceaccount "${SA_NAME}" -n default >/dev/null 2>&1 \
    || kubectl create serviceaccount "${SA_NAME}" -n default
kubectl get clusterrolebinding autage-ro >/dev/null 2>&1 \
    || kubectl create clusterrolebinding autage-ro \
        --clusterrole=view --serviceaccount="default:${SA_NAME}"

# ── the deliberately broken app ──────────────────────────────────────────────
# stress-ng demands more memory than the pod's limit allows → Kubernetes kills
# it (OOMKill), it restarts, dies again… a real crash-loop for Autage to diagnose.
info "Deploying the crashing 'auth-service' app into namespace '${NAMESPACE}'…"
kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"
if ! kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    kubectl create deployment "${DEPLOYMENT}" -n "${NAMESPACE}" \
        --image=polinux/stress-ng \
        -- stress-ng --vm 1 --vm-bytes 250M --vm-hang 0
fi
kubectl -n "${NAMESPACE}" set resources deploy/"${DEPLOYMENT}" --limits=memory=100Mi >/dev/null

# ── verify the bot account is genuinely read-only ────────────────────────────
info "Verifying the ServiceAccount cannot read Secrets, exec, or write..."
bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/verify_k8s_readonly.sh"

# ── credentials ──────────────────────────────────────────────────────────────
info "Issuing ${TOKEN_DURATION} read-only token…"
TOKEN="$(kubectl create token "${SA_NAME}" -n default --duration="${TOKEN_DURATION}")"
HOST_PORT="$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' | sed -E 's|https://127\.0\.0\.1:([0-9]+).*|\1|')"
CA_CERT="$(kubectl config view --raw --flatten -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 --decode)"

if [[ "${1:-}" == "--token" ]];
then
    printf 'SERVER_URL=%s\nTOKEN=%s\nCA_CERT=<see: kubectl config view --raw --flatten -o jsonpath="{.clusters[0].cluster.certificate-authority-data}" | base64 --decode>\n' "https://host.docker.internal:${HOST_PORT}" "${TOKEN}"
    exit 0
fi

cat <<EOF

============================================================
  Cluster ready! Now connect Autage - exactly 3 values:
============================================================

  1. Dashboard (http://localhost:5173) -> Settings -> Kubernetes, and save:

       Server URL:  https://host.docker.internal:${HOST_PORT}
       (use host.docker.internal - NOT 127.0.0.1 - because Autage itself
        runs inside Docker)

       Token:       (printed below - paste the WHOLE line)

       CA Cert:     (printed below - paste the WHOLE PEM block, all lines
                     from -----BEGIN CERTIFICATE----- to -----END CERTIFICATE-----)
       TLS is always verified against this certificate - the connection
       is rejected without it. This is the same 'curl --cacert' check:
       it proves the server is genuinely YOUR cluster.

     Click 'Test connection' -> should say TLS-verified 'Connected'.

  2. Trigger an alert:  uv run python scripts/send_mock_alert.py --live

============================================================

TOKEN (whole line, starts with 'eyJ'):

${TOKEN}

CA CERTIFICATE (whole block, BEGIN and END lines included):

${CA_CERT}

Cross-check it yourself with:
    kubectl get pods -n ${NAMESPACE}                # the crashing pod
    kubectl logs -n ${NAMESPACE} deploy/${DEPLOYMENT} --previous

Tear everything down later with:
    bash scripts/setup_kind_cluster.sh --destroy
EOF

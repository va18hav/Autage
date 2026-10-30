#!/usr/bin/env bash
# Verify that a Kubernetes ServiceAccount can read but cannot mutate or read Secrets.
set -euo pipefail

SA_NAMESPACE="${SA_NAMESPACE:-default}"
SA_NAME="${SA_NAME:-autage-ro}"
TARGET_NAMESPACE="${TARGET_NAMESPACE:-production}"
OUTPUT_FILE="${OUTPUT_FILE:-}"
SA_USER="system:serviceaccount:${SA_NAMESPACE}:${SA_NAME}"

info() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mxx>\033[0m %s\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }
have kubectl || fail "kubectl is not installed."

check() {
    local expected="$1"
    local verb="$2"
    local resource="$3"
    local answer=""

    # The built-in `view` role is aggregation-based. Immediately after cluster
    # creation its rules may not have propagated yet, so allow a short retry.
    for _attempt in $(seq 1 10); do
        answer="$(
            kubectl auth can-i "$verb" "$resource" \
                --namespace "$TARGET_NAMESPACE" \
                --as "$SA_USER" 2>/dev/null || true
        )"
        [[ "$answer" == "$expected" ]] && break
        sleep 1
    done

    if [[ "$answer" != "$expected" ]]; then
        fail "Expected '${verb} ${resource}' to be '${expected}', got '${answer:-error}'."
    fi

    printf '  %-4s %-8s %s\n' "$expected" "$verb" "$resource"
}

info "Checking read-only access for ${SA_USER} in namespace ${TARGET_NAMESPACE}"

printf '\nAllowed reads:\n'
check yes get pods
check yes list pods
check yes watch pods
check yes get pods/log
check yes get deployments
check yes list deployments
check yes watch deployments

printf '\nDenied operations:\n'
check no get secrets
check no list secrets
check no create pods/exec
check no create pods
check no delete pods
check no update deployments
check no patch deployments
check no delete deployments
check no create configmaps
check no delete configmaps

if [[ -n "$OUTPUT_FILE" ]]; then
    kubectl auth can-i --list \
        --namespace "$TARGET_NAMESPACE" \
        --as "$SA_USER" \
        > "$OUTPUT_FILE"
    chmod 600 "$OUTPUT_FILE"
    info "Saved full authorization listing to ${OUTPUT_FILE}"
fi

info "PASS: ServiceAccount is read-only and cannot read Secrets or exec into pods."

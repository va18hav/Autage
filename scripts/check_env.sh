#!/usr/bin/env bash
# Check local deployment env-file hygiene without printing secret values.
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"

info() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mxx>\033[0m %s\n' "$*" >&2; exit 1; }

[[ -f "$ENV_FILE" ]] || fail "${ENV_FILE} does not exist. Copy .env.example first."

mode="$(
    stat -f '%Lp' "$ENV_FILE" 2>/dev/null \
        || stat -c '%a' "$ENV_FILE" 2>/dev/null \
        || true
)"
[[ "$mode" == "600" ]] || fail "${ENV_FILE} must be chmod 600 (currently ${mode:-unknown})."

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git check-ignore -q "$ENV_FILE" \
        || fail "${ENV_FILE} is not ignored by git. Add it to .gitignore before proceeding."
fi

read_value() {
    local key="$1"
    local line value
    line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 || true)"
    [[ -n "$line" ]] || { printf ''; return; }
    value="${line#*=}"
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    printf '%s' "$value"
}

for key in AUTAGE_SECRET_KEY JWT_SECRET_KEY DB_PASSWORD; do
    [[ -n "$(read_value "$key")" ]] || fail "${key} is missing or empty."
done

autage_secret="$(read_value AUTAGE_SECRET_KEY)"
jwt_secret="$(read_value JWT_SECRET_KEY)"
db_password="$(read_value DB_PASSWORD)"
setup_token="$(read_value AUTAGE_SETUP_TOKEN)"

[[ "$autage_secret" != "$jwt_secret" ]] \
    || fail "JWT_SECRET_KEY must be different from AUTAGE_SECRET_KEY."
[[ "$autage_secret" != "$db_password" ]] \
    || fail "DB_PASSWORD must be different from AUTAGE_SECRET_KEY."
[[ "$jwt_secret" != "$db_password" ]] \
    || fail "DB_PASSWORD must be different from JWT_SECRET_KEY."

if [[ -n "$setup_token" ]]; then
    [[ ${#setup_token} -ge 32 ]] \
        || fail "AUTAGE_SETUP_TOKEN must be at least 32 characters."
    [[ "$setup_token" != "$autage_secret" && "$setup_token" != "$jwt_secret" && "$setup_token" != "$db_password" ]] \
        || fail "AUTAGE_SETUP_TOKEN must be different from all other secrets."
fi

info "${ENV_FILE} permissions and required secrets look good."

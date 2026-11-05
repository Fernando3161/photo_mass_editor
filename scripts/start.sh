#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

port=8000
lan_host=""
check_only=0
while (($#)); do
    case "$1" in
        --port) port="${2:?Missing port}"; shift 2 ;;
        --lan-host) lan_host="${2:?Missing LAN host}"; shift 2 ;;
        --check) check_only=1; shift ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done
[[ "$port" =~ ^[0-9]+$ ]] && ((port >= 1 && port <= 65535)) || { echo 'Invalid port' >&2; exit 2; }
test -f requirements.lock && test -f frontend/package-lock.json || { echo 'Missing dependency lockfile' >&2; exit 1; }
mkdir -p data/input data/catalog data/exports data/backups data/evidence data/models
if test -x .venv/bin/python; then
    .venv/bin/python scripts/setup_env.py
else
    python3 scripts/setup_env.py
fi
test -x .venv/bin/python || { echo 'Canonical .venv is missing' >&2; exit 1; }
.venv/bin/python -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()"
.venv/bin/python scripts/frontend_bundle.py
.venv/bin/python -c 'from pathlib import Path; from backend.review.__main__ import prepare_catalog; prepare_catalog(Path("data/catalog"))'
if ((check_only)); then echo 'Linux startup checks passed; server was not started.'; exit 0; fi

bind_host=127.0.0.1
allowed_hosts=localhost,127.0.0.1
if test -n "$lan_host"; then
    [[ "$lan_host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Use an IPv4 address for --lan-host' >&2; exit 2; }
    bind_host=0.0.0.0
    allowed_hosts="$allowed_hosts,$lan_host"
fi
export PHOTO_EDITOR_ALLOWED_HOSTS="$allowed_hosts"
export PHOTO_EDITOR_ACCESS_PASSWORD="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(24))')"
printf 'Local: http://127.0.0.1:%s/\nUsername: owner\nPassword for this run: %s\n' "$port" "$PHOTO_EDITOR_ACCESS_PASSWORD"
if test -n "$lan_host"; then
    printf 'LAN: http://%s:%s/\nUse only on a trusted private network; HTTP is unencrypted.\n' "$lan_host" "$port"
fi
.venv/bin/python -m backend.review --data-dir data/catalog --host "$bind_host" --port "$port"

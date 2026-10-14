#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d frontend/node_modules ]; then (cd frontend && npm ci --no-audit --no-fund); fi
(cd frontend && npm run build)
exec python3 -m backend.server --port "${PORT:-8000}"

#!/usr/bin/env bash
set -euo pipefail

case "${APP_COMPONENT:-all}" in
  backend)
    exec ./scripts/start_backend.sh
    ;;
  frontend)
    exec ./scripts/start_frontend.sh
    ;;
  all)
    ./scripts/start_backend.sh &
    API_PID=$!
    cleanup() {
      kill "$API_PID" 2>/dev/null || true
    }
    trap cleanup EXIT
    exec ./scripts/start_frontend.sh
    ;;
  *)
    echo "Unknown APP_COMPONENT=${APP_COMPONENT}. Use backend, frontend, or all."
    exit 1
    ;;
esac

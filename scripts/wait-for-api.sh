#!/usr/bin/env bash
# Wait until RagStack API liveness succeeds.
set -euo pipefail
url="${1:-http://localhost:8000/health}"
attempts="${2:-60}"
for i in $(seq 1 "$attempts"); do
  if curl -fsS "$url" >/dev/null 2>&1; then
    echo "ready: $url"
    exit 0
  fi
  sleep 2
done
echo "timed out waiting for $url" >&2
exit 1

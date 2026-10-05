#!/bin/bash
set -euo pipefail
checkpoint_root="$(cd "$(dirname "$0")/.." && pwd)"
if [ -x "$checkpoint_root/.tools/python3" ]; then
  exec "$checkpoint_root/.tools/python3" -B "$checkpoint_root/scripts/checkpoint.py" "$@"
fi
exec python3 -B "$checkpoint_root/scripts/checkpoint.py" "$@"

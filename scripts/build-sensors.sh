#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f /.dockerenv ]]; then
  echo "Run ./scripts/setup.sh build-drivers from the host repository root." >&2
  exit 2
fi
exec "${ROOT}/scripts/setup.sh" build-drivers

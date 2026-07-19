#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
command -v node >/dev/null 2>&1 || { echo "Node.js 20.9+ is required."; exit 1; }
[ -f out/index.html ] || { echo "Missing out/index.html. Run ./build.sh first."; exit 1; }
exec node scripts/serve-static.mjs 4173 --open

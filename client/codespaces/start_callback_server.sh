#!/usr/bin/env bash
# Avvia il callback server dentro GitHub Codespaces.
# Eseguire dalla cartella client/codespaces: bash start_callback_server.sh

set -euo pipefail

CLIENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CLIENT_DIR"

python3 callback_server.py --config callback_server.json --host 0.0.0.0 --port 8000

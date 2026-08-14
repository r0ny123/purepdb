#!/usr/bin/env bash
set -euo pipefail

VENV_BIN="$(cd "$(dirname "$0")/../.." && pwd)/.venv/bin"
PATH_LINE="export PATH=\"${VENV_BIN}:\$PATH\""

if [[ -d "$VENV_BIN" ]]; then
  if ! grep -qF "$VENV_BIN" "$HOME/.bashrc" 2>/dev/null; then
    echo "$PATH_LINE" >>"$HOME/.bashrc"
  fi
  export PATH="${VENV_BIN}:${PATH}"
fi

#!/usr/bin/env bash
set -euo pipefail

RECREATE=true
INSTALL_SPACY=false

for arg in "$@"; do
  case "$arg" in
    --no-recreate)
      RECREATE=false
      ;;
    --install-spacy)
      INSTALL_SPACY=true
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-clean"

if [[ "$RECREATE" == "true" && -d "$VENV_DIR" ]]; then
  echo "[bootstrap] Removing existing .venv-clean"
  rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_CMD="python3.11"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
  else
    echo "Python is not installed. Install Python 3.11 and rerun."
    exit 1
  fi

  echo "[bootstrap] Creating .venv-clean"
  "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

PY="$VENV_DIR/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "Virtual environment python not found at $PY"
  exit 1
fi

echo "[bootstrap] Installing backend dependencies"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r "$ROOT_DIR/backend/requirements.txt"

if [[ "$INSTALL_SPACY" == "true" ]]; then
  echo "[bootstrap] Installing spaCy model en_core_web_sm"
  "$PY" -m spacy download en_core_web_sm
fi

echo
echo "Bootstrap complete."
echo "Start backend with:"
echo "  cd backend && ../.venv-clean/bin/python -m uvicorn main:app --reload"

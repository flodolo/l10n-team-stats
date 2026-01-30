#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: 'uv' not found."
  exit 1
fi
if [[ ! -d "$VENV_DIR" ]]; then
  uv venv "$VENV_DIR"
fi
uv pip install -r requirements.txt

if [[ -f "./weekly_report.sh" ]]; then
  chmod +x ./weekly_report.sh
  uv run ./weekly_report.sh "$@"
else
  echo "Error: ./weekly_report.sh not found."
  exit 1
fi

uv run python scripts/export_to_gsheets.py
uv run python scripts/jira_requests_data.py
uv run python scripts/jira_vendors_data.py

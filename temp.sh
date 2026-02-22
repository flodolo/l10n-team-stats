#!/usr/bin/env bash
set -euo pipefail

START_DATE="2025-10-03"
END_DATE="2026-02-13"

python3 - <<'PY' | while IFS= read -r d; do
from datetime import date, timedelta

start = date.fromisoformat("2025-10-03")
end   = date.fromisoformat("2026-02-13")

d = start
while d <= end:
    print(d.isoformat())
    d += timedelta(days=7)
PY
  echo "Running for $d"
  uv run scripts/phabricator_user_activity.py --start "$d"
  uv run scripts/phabricator_group_activity.py --start "$d"
done

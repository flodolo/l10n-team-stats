#!/usr/bin/env bash

set -Eeu

interrupt_code() {
  printf "\n*** Operation interrupted ***\n"
  exit $?
}

trap interrupt_code SIGINT

script_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Optional --start argument
ARGS=()
if [[ $# -ge 1 ]]; then
  ARGS+=(--start "$1")
fi

section() {
  echo -e "\n--------------\n"
  echo "$1"
}

run_py() {
  local script_name=$1
  shift
  python "${script_path}/scripts/${script_name}" "$@" ${ARGS[@]+"${ARGS[@]}"}
}

section "Pontoon PR stats"
run_py "github_prs_stats.py" --repo mozilla/pontoon

section "Pontoon issues stats"
run_py "github_pontoon_issues_stats.py"

section "Jira stats"
run_py "jira_l10n_stats.py"

section "Phabricator stats"
run_py "phabricator_user_activity.py"
run_py "phabricator_group_activity.py"

section "GitHub EPM review stats"
run_py "github_review_stats_weekly.py"

section "Jira vendor stats"
run_py "jira_vendors_stats.py"

section "Jira request stats"
run_py "jira_requests_stats.py"

# Export to Google Sheets
run_py "export_to_sheets.py"
run_py "jira_requests_data.py"
run_py "jira_vendors_data.py"

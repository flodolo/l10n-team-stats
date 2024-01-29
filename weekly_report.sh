#! /usr/bin/env bash

function interrupt_code()
# This code runs if user hits control-c
{
  printf "\n*** Operation interrupted ***\n"
  exit $?
}

# Trap keyboard interrupt (control-c)
trap interrupt_code SIGINT

script_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pontoon stats
echo -e "\n--------------\n"
echo "Pontoon PR stats"
python "${script_path}/scripts/github_prs_stats.py" --since $1 --repo mozilla/pontoon

echo -e "\n--------------\n"
echo "Pontoon issues stats"
python "${script_path}/scripts/github_issues_stats.py" --since $1 --repo mozilla/pontoon

# Jira stats
echo -e "\n--------------\n"
echo "Jira stats"
python "${script_path}/scripts/jira_l10n_stats.py" --since $1

# Phabricator stats
echo -e "\n--------------\n"
echo "Phabricator stats"
python "${script_path}/scripts/phabricator_l10n_activity.py" --since $1

# GitHub review stats
echo -e "\n--------------\n"
echo "GitHub EPM review stats"
python "${script_path}/scripts/github_review_stats_weekly.py" --since $1

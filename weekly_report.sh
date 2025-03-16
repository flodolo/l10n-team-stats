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
if [ $# -eq 0 ]; then
  python "${script_path}/scripts/github_prs_stats.py" --repo mozilla/pontoon
else
  python "${script_path}/scripts/github_prs_stats.py" --start $1 --repo mozilla/pontoon
fi

echo -e "\n--------------\n"
echo "Pontoon issues stats"
if [ $# -eq 0 ]; then
  python "${script_path}/scripts/github_pontoon_issues_stats.py"
else
  python "${script_path}/scripts/github_pontoon_issues_stats.py" --start $1
fi

# Jira stats
echo -e "\n--------------\n"
echo "Jira stats"
if [ $# -eq 0 ]; then
  python "${script_path}/scripts/jira_l10n_stats.py"
else
  python "${script_path}/scripts/jira_l10n_stats.py" --start $1
fi

# Phabricator stats
echo -e "\n--------------\n"
echo "Phabricator stats"
if [ $# -eq 0 ]; then
  python "${script_path}/scripts/phabricator_l10n_activity.py"
  python "${script_path}/scripts/phabricator_group_activity.py"
else
  python "${script_path}/scripts/phabricator_l10n_activity.py" --start $1
  python "${script_path}/scripts/phabricator_group_activity.py" --start $1
fi

# GitHub review stats
echo -e "\n--------------\n"
echo "GitHub EPM review stats"
if [ $# -eq 0 ]; then
  python "${script_path}/scripts/github_review_stats_weekly.py"
else
  python "${script_path}/scripts/github_review_stats_weekly.py" --start $1
fi

# Jira vendor stats
echo -e "\n--------------\n"
echo "Jira vendor stats"
if [ $# -eq 0 ]; then
  python "${script_path}/scripts/jira_vendors_stats.py"
else
  python "${script_path}/scripts/jira_vendors_stats.py" --start $1
fi

# Jira request stats
echo -e "\n--------------\n"
echo "Jira vendor stats"
if [ $# -eq 0 ]; then
  python "${script_path}/scripts/jira_requests_stats.py"
else
  python "${script_path}/scripts/jira_requests_stats.py" --start $1
fi

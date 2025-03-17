#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
from functions import (
    get_jira_object,
    parse_arguments,
    search_jira_issues,
    store_json_data,
)


def print_issues(issues):
    for issue in issues:
        date_created = datetime.datetime.strptime(
            issue.fields.created, "%Y-%m-%dT%H:%M:%S.%f%z"
        ).strftime("%Y-%m-%d")
        if issue.fields.resolutiondate:
            date_resolved = datetime.datetime.strptime(
                issue.fields.resolutiondate, "%Y-%m-%dT%H:%M:%S.%f%z"
            ).strftime("%Y-%m-%d")
        else:
            date_resolved = "-"
        print(f"\nID: {issue.key}")
        print(f"Created on: {date_created} - Closed on: {date_resolved}")
        assignee = issue.fields.assignee.displayName if issue.fields.assignee else "-"
        print(f"Assignee: {assignee}")
        print(f"Summary: {issue.fields.summary}")
        # print(f"Due date: {issue.fields.customfield_10451}")


def build_summary(issues, type, summary, summary_output, project):
    if not issues:
        summary_output[type].append(f"  - {project}: no issues")
        return

    ids = []
    for issue in issues:
        ids.append(issue.key)
    ids.sort()
    summary[type]["issues"].extend(ids)

    summary_output[type].append(f"  - {project}: {len(ids)} issues ({', '.join(ids)})")


def main():
    args = parse_arguments()
    str_since_date = args.start.strftime("%Y-%m-%d")
    end_date = args.end
    str_end_date = end_date.strftime("%Y-%m-%d")

    jira = get_jira_object()
    record = {}

    summary = {
        "backlog": {"label": "in backlog", "issues": []},
        "blocked": {"label": "blocked", "issues": []},
        "closed": {
            "label": f"closed between {str_since_date} and {str_end_date}",
            "issues": [],
        },
        "created": {
            "label": f"opened between {str_since_date} and {str_end_date}",
            "issues": [],
        },
        "in-progress": {"label": "in progress", "issues": []},
    }
    summary_output = {
        "backlog": ["Issues in backlog for:"],
        "blocked": ["Issues blocked for:"],
        "closed": [f"Issues closed between {str_since_date} and {str_end_date} for:"],
        "created": [f"Issues created between {str_since_date} and {str_end_date} for:"],
        "in-progress": ["Issues in progress for:"],
    }
    projects = ["l10n-requests", "l10n-vendor"]

    ## Backlog
    backlog = search_jira_issues(
        jira,
        "project=l10n-requests AND status=Backlog ORDER BY created DESC",
    )
    build_summary(backlog, "backlog", summary, summary_output, "l10n-requests")
    if args.verbose:
        print_issues(backlog)

    # l10n-vendors has open epics that are not pending work
    backlog = search_jira_issues(
        jira,
        "project=l10n-vendor AND status in (Backlog, 'To Do') AND issuetype != Epic ORDER BY created DESC",
    )
    build_summary(backlog, "backlog", summary, summary_output, "l10n-vendors")
    if args.verbose:
        print_issues(backlog)

    # l10n-requests has also a blocked status
    blocked = search_jira_issues(
        jira,
        "project=l10n-requests AND status ='Blocked' ORDER BY created DESC",
    )
    build_summary(blocked, "blocked", summary, summary_output, "l10n-requests")
    if args.verbose:
        print_issues(blocked)

    for project in projects:
        in_progress = search_jira_issues(
            jira,
            f"project={project} AND status='In Progress' ORDER BY created DESC",
        )
        build_summary(in_progress, "in-progress", summary, summary_output, project)
        if args.verbose:
            print_issues(in_progress)

        date_since = args.start.strftime("%Y-%m-%d")
        created = search_jira_issues(
            jira,
            f"project={project} AND created>={date_since} ORDER BY created DESC",
        )
        build_summary(created, "created", summary, summary_output, project)
        if args.verbose:
            print_issues(created)

        closed = search_jira_issues(
            jira,
            f"project={project} AND resolutiondate>={date_since} ORDER BY created DESC",
        )
        build_summary(created, "closed", summary, summary_output, project)
        if args.verbose:
            print_issues(closed)

    for lines in summary_output.values():
        print("")
        print("\n".join(lines))

    print("\n--------\n")
    for category in summary.values():
        status = category["label"]
        ids = category["issues"]
        if not ids:
            print(f"No issues {status}.")
        else:
            print(f"Issues {status} ({len(ids)}): {', '.join(ids)}")

    for k, v in summary.items():
        record[k] = len(v["issues"])
    store_json_data("jira-issues", record, day=end_date)


if __name__ == "__main__":
    main()

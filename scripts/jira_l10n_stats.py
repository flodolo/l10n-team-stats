#! /usr/bin/env python3

import datetime
from functions import get_jira_object, parse_arguments


def search_issues(connection, query):
    pagesize = 100
    index = 0
    issues = []
    while True:
        startAt = index * pagesize
        # _issues = jira.search_issues('project=FXA and created > startOfDay(-5) order by id desc', startAt=startAt, maxResults=chunk)
        _issues = connection.search_issues(
            query,
            startAt=startAt,
            maxResults=pagesize,
        )
        if _issues:
            issues.extend(_issues)
            index += 1
        else:
            break

    return issues


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
    since_date = args.since.strftime("%Y-%m-%d")

    jira = get_jira_object()

    summary = {
        "backlog": {"label": "in backlog", "issues": []},
        "in-progress": {"label": "in progress", "issues": []},
        "created": {"label": f"opened since {since_date}", "issues": []},
        "closed": {"label": f"closed since {since_date}", "issues": []},
    }
    summary_output = {
        "backlog": ["Issues in backlog for:"],
        "in-progress": ["Issues in progress for:"],
        "created": [f"Issues created since {since_date} for:"],
        "closed": [f"Issues closed since {since_date} for:"],
    }
    projects = ["l10n-requests", "l10n-vendor"]

    ## Backlog
    backlog = search_issues(
        jira,
        f"project=l10n-requests AND status=Backlog ORDER BY created DESC",
    )
    build_summary(backlog, "backlog", summary, summary_output, "l10n-requests")
    if args.verbose:
        print_issues(backlog)

    # l10n-vendors has open epics that are not pending work
    backlog = search_issues(
        jira,
        f"project=l10n-vendor AND status in (Backlog, 'To Do') AND issuetype != Epic ORDER BY created DESC",
    )
    build_summary(backlog, "backlog", summary, summary_output, "l10n-vendors")
    if args.verbose:
        print_issues(backlog)

    for project in projects:
        in_progress = search_issues(
            jira,
            f"project={project} AND status='In Progress' ORDER BY created DESC",
        )
        build_summary(in_progress, "in-progress", summary, summary_output, project)
        if args.verbose:
            print_issues(in_progress)

        date_since = args.since.strftime("%Y-%m-%d")
        created = search_issues(
            jira,
            f"project={project} AND created>={date_since} ORDER BY created DESC",
        )
        build_summary(created, "created", summary, summary_output, project)
        if args.verbose:
            print_issues(created)

        closed = search_issues(
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


if __name__ == "__main__":
    main()
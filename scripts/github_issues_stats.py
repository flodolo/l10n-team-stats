#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from functions import format_avg_time, get_github_object, parse_arguments


def main():
    args = parse_arguments(repo=True)
    date_since = args.since.strftime("%Y-%m-%d")
    repo = args.repo

    g = get_github_object()

    print(f"Analysis of repository: {repo}\n")

    # Analyze all open PRs
    stats = {
        "Total": 0,
        "P1": 0,
        "P2": 0,
        "P3": 0,
        "P4": 0,
        "P5": 0,
    }

    open = g.search_issues(
        query=f"repo:{repo} is:issue is:open",
        sort="created",
        order="desc",
    )
    if open:
        for pr in open:
            stats["Total"] += 1
            for label in pr.labels:
                if label.name in stats.keys():
                    stats[label.name] += 1

        print("Overall statistics about open issues:")
        for k, v in stats.items():
            print(f"- {k}: {v}")

    # Analyze PRs opened since the specified date
    opened = g.search_issues(
        query=f"repo:{repo} is:issue created:>={date_since}",
        sort="created",
        order="desc",
    )
    if opened:
        issues = {}
        for issue in opened:
            created_at = issue.created_at.strftime("%Y-%m-%d")
            labels = [
                label.name for label in issue.labels if label.name.startswith("P")
            ]
            label = labels[0] if len(labels) > 0 else "-"
            issues[f"#{issue.number}"] = (
                f"  - #{issue.number} {created_at}: ({label}) {issue.title}"
            )
        issue_ids = list(issues.keys())
        print(
            f"Issues opened after {date_since} ({len(issue_ids)}): {', '.join(issue_ids)}"
        )
        if args.verbose:
            print("\n".join(issues.values()))

    # Analyze PRs closed since the specified date
    closed = g.search_issues(
        query=f"repo:{repo} is:issue closed:>={date_since}",
        sort="created",
        order="desc",
    )
    if closed:
        issues = {}
        age = 0
        for issue in closed:
            closed_at = issue.closed_at.strftime("%Y-%m-%d")
            age += (issue.closed_at - issue.created_at).total_seconds()
            labels = [
                label.name for label in issue.labels if label.name.startswith("P")
            ]
            label = labels[0] if len(labels) > 0 else "-"
            issues[f"#{issue.number}"] = (
                f"  - #{issue.number} {closed_at}: ({label}) {issue.title}"
            )
        issue_ids = list(issues.keys())
        count = len(issue_ids)
        avg_age = round(age / count)
        print(f"Issues closed after {date_since} ({count}): {', '.join(issue_ids)}")
        print(f"Average age of closed issues: {format_avg_time(avg_age)}")
        if args.verbose:
            print("\n".join(issues.values()))


if __name__ == "__main__":
    main()

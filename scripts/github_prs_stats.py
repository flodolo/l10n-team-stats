#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import datetime, timezone
from functions import get_github_object, parse_arguments, format_time


def main():
    args = parse_arguments(repo=True)
    date_since = args.since.strftime("%Y-%m-%d")
    repo = args.repo

    g = get_github_object()

    ## Opened pull requests
    opened = g.search_issues(
        query=f"repo:{repo} is:pr is:open created:>={date_since}",
        sort="created",
        order="desc",
    )

    if opened:
        prs = []
        for pr in opened:
            created_at = pr.created_at.strftime("%Y-%m-%d")
            prs.append(f"#{pr.number} ({created_at})")

            if args.verbose:
                print(f"Number: #{pr.number}")
                print(f"Created: {created_at}")

        count = len(prs)
        print(f"Opened PRs since {date_since} ({count}): {', '.join(prs)}")

    ## Closed pull requests
    closed = g.search_issues(
        query=f"repo:{repo} is:pr is:closed closed:>={date_since}",
        sort="created",
        order="desc",
    )

    if closed:
        overall_time = 0
        prs = []
        for pr in closed:
            closed_at = pr.closed_at.strftime("%Y-%m-%d")
            time_to_close = (pr.closed_at - pr.created_at).total_seconds()
            overall_time += time_to_close
            prs.append(f"#{pr.number} ({closed_at})")

            if args.verbose:
                print(f"Number: #{pr.number}")
                print(f"Created: {pr.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Closed: {closed_at}")
                print(f"Time to close: {format_time(time_to_close)}")

        count = len(prs)
        avg_time = round(overall_time / count) if count > 0 else 0
        print(f"Closed PRs since {date_since} ({count}): {', '.join(prs)}")
        if avg_time > 0:
            print(f"Average time to close: {format_time(avg_time)}")

    ## Open pull requests
    open = g.search_issues(
        query=f"repo:{repo} is:pr is:open",
        sort="created",
        order="desc",
    )

    if open:
        prs = []
        age = 0
        today = datetime.now(timezone.utc)
        for pr in open:
            created_at = pr.created_at.strftime("%Y-%m-%d")
            prs.append(f"#{pr.number} ({created_at})")
            pr_age = (today - pr.created_at).total_seconds()
            age += pr_age
            if args.verbose:
                print(f"Number: #{pr.number}")
                print(f"Created: {created_at}")
                print(f"Age: {format_time(pr_age)}")
        count = len(prs)
        avg_age = round(age / count) if count > 0 else 0
        print(f"Open PRs as of {today.strftime('%Y-%m-%d')}: {count}")
        if avg_age > 0:
            print(f"Average age: {format_time(avg_age)}")


if __name__ == "__main__":
    main()

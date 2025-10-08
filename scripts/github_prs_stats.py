#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import datetime, timezone

from functions import (
    format_time,
    get_github_object,
    parse_arguments,
    store_json_data,
)


def main():
    args = parse_arguments(repo=True)
    str_start_date = args.start.strftime("%Y-%m-%d")
    end_date = args.end
    str_end_date = end_date.strftime("%Y-%m-%d")
    repo = args.repo

    g = get_github_object()
    record = {}

    # Opened pull requests.
    opened = g.search_issues(
        query=f"repo:{repo} is:pr created:{str_start_date}..{str_end_date}",
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
        print(
            f"Opened PRs between {str_start_date} and {str_end_date} ({count}): {', '.join(prs)}"
        )
        record["opened"] = count

    # Closed pull requests.
    closed = g.search_issues(
        query=f"repo:{repo} is:pr is:closed closed:{str_start_date}..{str_end_date}",
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
        print(
            f"Closed PRs between {str_start_date} and {str_end_date} ({count}): {', '.join(prs)}"
        )
        record["closed"] = count
        # Store value in hours.
        record["avg-time-to-close"] = round(avg_time / 3600, 1)
        if avg_time > 0:
            print(f"Average time to close: {format_time(avg_time)}")

    # Pull requests currently open.
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
        record["open"] = count
        # Store value in hours.
        record["avg-age-open"] = round(avg_age / 3600, 1)
        print(f"Open PRs as of {today.strftime('%Y-%m-%d')}: {count}")
        if avg_age > 0:
            print(f"Average age: {format_time(avg_age)}")

    store_json_data("pontoon-prs", record, day=end_date)


if __name__ == "__main__":
    main()

#! /usr/bin/env python3

import calendar

from collections import defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from functions import format_time, get_gh_usernames, get_pr_details, parse_arguments


def main():
    args = parse_arguments(repo=True, user=True)
    start_date = args.start
    end_date = args.end

    if args.user:
        usernames = {args.user: args.user}
    else:
        usernames = get_gh_usernames()
    repo = args.repo

    periods = []
    d = start_date
    while d < end_date:
        periods.append(d)
        d += relativedelta(months=1)

    overall_data = defaultdict(lambda: defaultdict(dict))
    for d in periods:
        period_name = f"{d.year}-{d.month:02}"
        period_start = datetime(d.year, d.month, 1, 0, 0, 0)
        period_end = datetime(
            d.year, d.month, calendar.monthrange(d.year, d.month)[1], 23, 59, 59
        )
        pr_stats = defaultdict(lambda: defaultdict(dict))
        get_pr_details(
            [repo],
            usernames,
            period_start,
            period_end,
            pr_stats,
            single_repo=True,
        )
        overall_data[period_name] = pr_stats

    overall_stats = {
        "max_review": 0,
        "max_close": 0,
        "total_time_reviews": 0,
        "total_reviews": 0,
        "total_authored": 0,
    }
    for period_name, period_data in overall_data.items():
        print("\n-----------\n")
        print(f"Period: {period_name}")

        print(f"\nRepository: {repo}")
        # Get number of PRs reviewed, time to review
        for username, repo_times in period_data["review_times"].items():
            times = repo_times.get(repo, None)
            if times:
                max_time = max(times)
                avg = round(sum(times) / len(times))

                overall_stats["total_time_reviews"] += sum(times)
                if max_time > overall_stats["max_review"]:
                    overall_stats["max_review"] = max_time

                print(
                    f"- {usernames[username]}: {len(times)} (avg review time: {format_time(avg)}, max time: {format_time(max_time)})"
                )
                overall_stats["total_reviews"] += len(times)

        # Get max time to close PRs
        for username, times in period_data["pr_closed"].items():
            if times:
                max_time = max(times)
                if max_time > overall_stats["max_close"]:
                    overall_stats["max_close"] = max_time

        # Get total number of authored PRs
        for username, prs in period_data["pr_authored"].items():
            overall_stats["total_authored"] += len(prs)

    if overall_stats["total_reviews"] > 0:
        average = round(
            overall_stats["total_time_reviews"] / overall_stats["total_reviews"]
        )
    else:
        average = 0
    print(f"\nAverage time to review: {format_time(average)}")
    print(f"Max time to review a PR: {format_time(overall_stats['max_review'])}")
    print(f"Max time to close a PR: {format_time(overall_stats['max_close'])}")

    print(f"Total reviewed: {overall_stats['total_reviews']}")
    if overall_stats["total_authored"] > 0:
        print(f"Total authored: {overall_stats['total_authored']}")


if __name__ == "__main__":
    main()

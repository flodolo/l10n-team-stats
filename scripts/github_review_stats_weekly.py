#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import defaultdict

from functions import (
    format_time,
    get_gh_usernames,
    get_user_pr_collection,
    get_pr_details,
    parse_arguments,
    store_json_data,
)


def main():
    args = parse_arguments()
    start_date = args.start

    usernames = get_gh_usernames()
    record = {}
    period_data = {
        "pr_created": defaultdict(lambda: defaultdict(dict)),
        "pr_reviewed": defaultdict(lambda: defaultdict(dict)),
        "repositories": set(),
    }

    get_user_pr_collection(period_data, start_date)

    # Extract data on avg time to review
    pr_stats = defaultdict(lambda: defaultdict(dict))

    # Get a list of all the repos and usernames with some data
    active_usernames = list(period_data["pr_reviewed"].keys())
    active_usernames.sort()

    repos = []
    for username in active_usernames:
        repos += list(period_data["pr_reviewed"][username].keys())
    repos = list(set(repos))
    repos.remove("total")
    repos.sort()

    get_pr_details(repos, active_usernames, start_date, pr_stats)

    print("\n-----------\n")
    for username, name in usernames.items():
        repos = pr_stats["review_times"][username]
        details = []
        total_reviews = period_data["pr_reviewed"][username]["total"]
        user_header = f"\nUser: {name} ({len(repos)}"
        user_header += " repository, " if len(repos) == 1 else " repositories,"
        user_header += f" {total_reviews}"
        user_header += " review, " if total_reviews == 1 else " reviews,"

        averages = []
        for repo, times in repos.items():
            avg = round(sum(times) / len(times))
            averages.append(avg)
            count = (
                period_data["pr_reviewed"][username][repo]
                if repo in period_data["pr_reviewed"][username]
                else 0
            )
            details.append(f"- {repo}: {count} (avg review time: {format_time(avg)})")

        avg_user = round(sum(averages) / len(averages)) if averages else 0
        user_header += f" avg review time {format_time(avg_user)})"
        print(user_header)
        print("\n".join(details))

    total_reviews = 0
    total_time = 0
    for user_data in pr_stats["review_times"].values():
        for repo, repo_data in user_data.items():
            total_reviews += len(repo_data)
            total_time += sum(x for x in repo_data)

    avg = round(total_time / total_reviews) if total_reviews > 0 else 0
    record["github-reviews"] = total_reviews
    # Store value in hours
    record["github-avg-time-to-review"] = round(avg / 3600, 1)
    record["github-repositories"] = len(period_data["repositories"])

    total_created = 0
    for user_data in period_data["pr_created"].values():
        total_created += user_data["total"]
    record["github-pr-created"] = total_created

    print(f"\nTotal reviews: {total_reviews}")
    if avg > 0:
        print(f"Average review time: {format_time(avg)}")
    print(f"\nNumber of pull requests created: {total_created}")
    print(f"\nNumber of repositories: {len(period_data['repositories'])}")

    store_json_data(start_date.strftime("%Y-%m-%d"), "epm-reviews", record, extend=True)


if __name__ == "__main__":
    main()

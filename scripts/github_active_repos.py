#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# List unique repositories where the given GitHub users opened or reviewed
# pull requests in the last N months (default: 3).

import argparse

from datetime import datetime, timedelta

from functions import github_api_request


USERNAMES = [
    "bcolsson",
    "camilapedraza",
    "eergunbinen",
    "flodolo",
    "ayshushus",
    "eemeli",
    "ewerybody",
    "mathjazz",
]


def get_active_repos(username, start_date):
    query = """
        query {
            user(login: "%USER%") {
                contributionsCollection(from: "%START%") {
                    pullRequestReviewContributionsByRepository(maxRepositories: 100) {
                        repository {
                            nameWithOwner
                        }
                    }
                    pullRequestContributionsByRepository(maxRepositories: 100) {
                        repository {
                            nameWithOwner
                        }
                    }
                }
            }
        }
    """
    replacements = {"%USER%": username, "%START%": start_date.isoformat()}
    for placeholder, value in replacements.items():
        query = query.replace(placeholder, value)

    r = github_api_request(query)
    user_data = r.json()["data"]["user"]
    if user_data is None:
        print(f"User not found: {username}")
        return set()

    json_data = user_data["contributionsCollection"]
    repos = set()
    for key in [
        "pullRequestReviewContributionsByRepository",
        "pullRequestContributionsByRepository",
    ]:
        for contrib in json_data[key]:
            repos.add(contrib["repository"]["nameWithOwner"])

    return repos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--months",
        "-m",
        type=int,
        default=3,
        help="Number of months to look back (default: 3)",
    )
    parser.add_argument(
        "--verbose", "-v", help="Print repositories for each user", action="store_true"
    )
    args = parser.parse_args()

    start_date = datetime.today() - timedelta(days=30 * args.months)
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    print(f"Requesting data since: {start_date.strftime('%Y-%m-%d')}")

    all_repos = set()
    for username in USERNAMES:
        try:
            repos = get_active_repos(username, start_date)
        except Exception as e:
            print(f"Error requesting data for {username}: {e}")
            continue
        if args.verbose:
            print(f"\nUser: {username} ({len(repos)})")
            for repo in sorted(repos):
                print(f"- {repo}")
        all_repos.update(repos)

    print(f"\nActive repositories ({len(all_repos)}):")
    for repo in sorted(all_repos, key=str.lower):
        print(repo)


if __name__ == "__main__":
    main()

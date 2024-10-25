#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import defaultdict
from datetime import datetime, timedelta

from functions import (
    format_avg_time,
    github_api_request,
    parse_arguments,
    store_json_data,
)


def query_pr_data(start_date, repo, usernames, query, pr_stats, cursor=""):
    repo_query = query.replace("%REPO%", repo)
    if cursor != "":
        repo_query = repo_query.replace("%CURSOR%", f'after: "{cursor}"')
    else:
        repo_query = repo_query.replace("%CURSOR%", "")

    r = github_api_request(repo_query)
    r_data = r.json()["data"]["search"]
    for node in r_data["nodes"]:
        for review_node in node["reviews"]["nodes"]:
            if review_node["author"] is None:
                continue
            author = review_node["author"]["login"]
            if author in usernames and review_node["state"] == "APPROVED":
                review_date = datetime.strptime(
                    review_node["submittedAt"], "%Y-%m-%dT%H:%M:%SZ"
                )
                if review_date <= start_date:
                    # Ignore review that happened the month before
                    continue

                review_time = review_date - datetime.strptime(
                    node["createdAt"], "%Y-%m-%dT%H:%M:%SZ"
                )
                if repo not in pr_stats[author]:
                    pr_stats[author][repo] = [review_time.total_seconds()]
                else:
                    pr_stats[author][repo].append(review_time.total_seconds())

    if r_data["pageInfo"]["hasNextPage"]:
        new_cursor = r_data["pageInfo"]["endCursor"]
        # print(f"  Requesting new page (from {new_cursor})")
        query_pr_data(start_date, repo, usernames, query, pr_stats, new_cursor)


def get_pr_data(period_data, start_date, pr_stats):
    query_prs = """
{
  search(
    first: 100
    query: "repo:%REPO% is:pr created:>=%START%"
    type: ISSUE
    %CURSOR%
  ) {
    nodes {
      ... on PullRequest {
        url
        createdAt
        closedAt
        merged
        reviewDecision
        reviews(first: 100) {
          nodes {
            author {
              login
            }
            submittedAt
            state
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      startCursor
      endCursor
    }
  }
}
"""

    start_query = start_date - timedelta(weeks=6)
    query_prs = query_prs.replace("%START%", start_query.strftime("%Y-%m-%d"))

    # Get a list of all the repos and usernames
    usernames = list(period_data.keys())
    usernames.sort()
    repos = []
    for username in usernames:
        repos += list(period_data[username].keys())
    repos = list(set(repos))
    repos.remove("total")
    repos.sort()

    for repo in repos:
        # print(f"Requesting data for {repo}")
        query_pr_data(start_date, repo, usernames, query_prs, pr_stats)


def main():
    args = parse_arguments()
    start_date = args.since

    usernames = {
        "bcolsson": "Bryan",
        "Delphine": "Delphine",
        "flodolo": "Flod",
        "peiying2": "Peiying",
    }
    record = {}
    repository_reviews = defaultdict(lambda: defaultdict(dict))
    repository_new_prs = defaultdict(lambda: defaultdict(dict))
    repositories = set()

    print(f"Requesting data since: {start_date.strftime('%Y-%m-%d')}")
    for username in usernames.keys():
        replacements = {"%USER%": username, "%START%": start_date.isoformat()}
        try:
            query = """
                query {
                    user(login: "%USER%") {
                        contributionsCollection(from: "%START%") {
                            pullRequestReviewContributionsByRepository(maxRepositories: 100) {
                                contributions {
                                    totalCount
                                }
                                repository {
                                    nameWithOwner
                                }
                            }
                            pullRequestContributionsByRepository(maxRepositories: 100) {
                                contributions {
                                    totalCount
                                }
                                repository {
                                    nameWithOwner
                                }
                            }
                        }
                    }
                }
            """
            for placeholder, value in replacements.items():
                query = query.replace(placeholder, value)
            r = github_api_request(query)
            json_data = r.json()["data"]["user"]["contributionsCollection"]

            # Get reviews
            total_reviewed = 0
            for contrib in json_data["pullRequestReviewContributionsByRepository"]:
                repo_name = contrib["repository"]["nameWithOwner"]
                repositories.add(repo_name)
                count = contrib["contributions"]["totalCount"]
                total_reviewed += count
                repository_reviews[username][repo_name] = count
            repository_reviews[username]["total"] = total_reviewed

            # Get PR opened
            total_created = 0
            for contrib in json_data["pullRequestContributionsByRepository"]:
                repo_name = contrib["repository"]["nameWithOwner"]
                repositories.add(repo_name)
                count = contrib["contributions"]["totalCount"]
                total_created += count
                repository_new_prs[username][repo_name] = count
            repository_new_prs[username]["total"] = total_created
        except Exception as e:
            print(e)

    # Extract data on avg time to review
    pr_stats = defaultdict(dict)
    get_pr_data(repository_reviews, start_date, pr_stats)

    print("\n-----------\n")
    for username, name in usernames.items():
        repos = pr_stats[username]
        details = []
        total_reviews = repository_reviews[username]["total"]
        user_header = f"\nUser: {name} ({len(repos)}"
        user_header += " repository, " if len(repos) == 1 else " repositories,"
        user_header += f" {total_reviews}"
        user_header += " review, " if total_reviews == 1 else " reviews,"

        averages = []
        for repo, times in repos.items():
            avg = round(sum(times) / len(times))
            averages.append(avg)
            count = (
                repository_reviews[username][repo]
                if repo in repository_reviews[username]
                else 0
            )
            details.append(
                f"- {repo}: {count} (avg review time: {format_avg_time(avg)})"
            )

        avg_user = round(sum(averages) / len(averages)) if averages else 0
        user_header += f" avg review time {format_avg_time(avg_user)})"
        print(user_header)
        print("\n".join(details))

    total_reviews = 0
    total_time = 0
    for user_data in pr_stats.values():
        for repo, repo_data in user_data.items():
            total_reviews += len(repo_data)
            total_time += sum(x for x in repo_data)

    avg = round(total_time / total_reviews) if total_reviews > 0 else 0
    record["github-reviews"] = total_reviews
    # Store value in hours
    record["github-avg-time-to-review"] = round(avg / 3600, 1)
    record["github-repositories"] = len(repositories)

    total_created = 0
    for user_data in repository_new_prs.values():
        total_created += user_data["total"]
    record["github-pr-created"] = total_created

    print(f"\nTotal reviews: {total_reviews}")
    if avg > 0:
        print(f"Average review time: {format_avg_time(avg)}")
    print(f"\nNumber of pull requests created: {total_created}")
    print(f"\nNumber of repositories: {len(repositories)}")

    store_json_data("epm-reviews", record, extend=True)


if __name__ == "__main__":
    main()

#! /usr/bin/env python3

from collections import defaultdict
from datetime import datetime, timedelta

from functions import format_avg_time, github_api_request, parse_arguments


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
    start_date = args.since.replace(hour=0, minute=0, second=0, microsecond=0)

    usernames = {
        "bcolsson": "Bryan",
        "Delphine": "Delphine",
        "flodolo": "Flod",
        "peiying2": "Peiying",
    }

    repository_contributions = defaultdict(lambda: defaultdict(dict))

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
                        }
                    }
                }
            """
            for placeholder, value in replacements.items():
                query = query.replace(placeholder, value)
            r = github_api_request(query)
            json_data = r.json()["data"]["user"]["contributionsCollection"][
                "pullRequestReviewContributionsByRepository"
            ]
            total = 0
            for contrib in json_data:
                repo_name = contrib["repository"]["nameWithOwner"]
                count = contrib["contributions"]["totalCount"]
                total += count
                repository_contributions[username][repo_name] = count
            repository_contributions[username]["total"] = total
        except Exception as e:
            print(e)

    # Extract data on avg time to resolve
    pr_stats = defaultdict(dict)
    get_pr_data(repository_contributions, start_date, pr_stats)

    print("\n-----------\n")
    for username, name in usernames.items():
        repos = pr_stats[username]
        details = []
        total_reviews = repository_contributions[username]["total"]
        user_header = f"\nUser: {name} ({len(repos)}"
        user_header += f" repository, " if len(repos) == 1 else f" repositories,"
        user_header += f" {total_reviews}"
        user_header += f" review, " if total_reviews == 1 else f" reviews,"

        averages = []
        for repo, times in repos.items():
            avg = round(sum(times) / len(times))
            averages.append(avg)
            count = (
                repository_contributions[username][repo]
                if repo in repository_contributions[username]
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

    avg = round(total_time / total_reviews)
    print(f"\nTotal reviews: {total_reviews}")
    print(f"Average review time: {format_avg_time(avg)}")


if __name__ == "__main__":
    main()

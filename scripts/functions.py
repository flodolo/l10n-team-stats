# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import datetime, time, timedelta
from github import Github
from jira import JIRA
import argparse
import configparser
import json
import os
import requests
import urllib.parse as url_parse
import urllib.request as url_request
import urllib3


def ymd(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid YYYY-MM-DD date: {value}")


def parse_arguments(
    repo=False,
    user=False,
    group=False,
    end_date=False,
):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start",
        "-s",
        type=ymd,
        help="Start date (YYYY-MM-DD, defaults to 1 week ago)",
    )
    parser.add_argument(
        "--verbose", "-v", help="Print list of revisions", action="store_true"
    )
    if repo:
        parser.add_argument(
            "--repo", "-r", help="Repository (e.g. mozilla/pontoon))", required=True
        )
    if end_date:
        parser.add_argument("--end", "-e", help="End date for analysis (YYYY-MM-DD)")
    if group:
        parser.add_argument("--group", "-g", help="Group name on Phabricator")
    if user:
        parser.add_argument("--user", "-u", help="Username on GitHub")
    args = parser.parse_args()

    if not args.start:
        args.start = datetime.today() - timedelta(weeks=1)
    args.start = args.start.replace(hour=0, minute=0, second=0, microsecond=0)

    if end_date:
        if args.end:
            args.end = datetime.strptime(args.end, "%Y-%m-%d")
            args.end = args.end.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
        else:
            args.end = datetime.now()

    return args


def read_config(key):
    # Read config file in the parent folder
    config_file = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
        "api_config.env",
    )
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_file)
    if key == "github":
        return config.get("KEYS", "GITHUB_TOKEN")

    if key == "jira":
        return (
            config.get("KEYS", "JIRA_EMAIL"),
            config.get("KEYS", "JIRA_TOKEN"),
            config.get("URLS", "JIRA_SERVER"),
        )

    if key == "phab":
        return (
            config.get("KEYS", "PHABRICATOR_TOKEN"),
            config.get("URLS", "PHABRICATOR_SERVER"),
        )

    if key == "gdocs":
        return dict(config.items("GDOCS"))


def format_time(interval):
    # Unit of measurement is seconds
    if interval < 3600:
        interval = round(interval / 60)
        return f"{interval} minute" if interval == 1 else f"{interval} minutes"
    elif interval < (86400 * 3):
        # Up to 3 days, display hours
        interval = round(interval / 3600)
        return f"{interval} hour" if interval == 1 else f"{interval} hours"
    else:
        interval = round(interval / 86400)
        return f"{interval} day" if interval == 1 else f"{interval} days"


def check_date_interval(start_date, end_date, timestamp):
    dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z")
    start_dt = datetime.combine(start_date, time.min).replace(tzinfo=dt.tzinfo)
    end_dt = datetime.combine(end_date, time.min).replace(tzinfo=dt.tzinfo)
    return start_dt <= dt <= end_dt


def get_github_object():
    github_token = read_config(key="github")
    return Github(
        github_token,
        retry=urllib3.util.retry.Retry(
            total=10, status_forcelist=(500, 502, 504), backoff_factor=0.3
        ),
    )


def github_api_request(query):
    url = "https://api.github.com/graphql"
    github_token = read_config(key="github")
    json_query = {"query": query}
    headers = {"Authorization": f"token {github_token}"}
    r = requests.post(url=url, json=json_query, headers=headers)

    return r


def get_jira_object():
    jira_email, jira_token, jira_server = read_config(key="jira")
    return JIRA(
        basic_auth=(jira_email, jira_token),
        server=jira_server,
    )


def search_jira_issues(connection, query, changelog=False):
    pagesize = 100
    index = 0
    issues = []
    while True:
        startAt = index * pagesize
        # _issues = jira.search_issues('project=FXA and created > startOfDay(-5) order by id desc', startAt=startAt, maxResults=chunk)
        if changelog:
            _issues = connection.search_issues(
                query,
                startAt=startAt,
                maxResults=pagesize,
                expand="changelog",
            )
        else:
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


def get_json_file():
    return os.path.join(os.path.dirname(__file__), os.pardir, "data", "data.json")


def get_json_data():
    json_file = get_json_file()
    if not os.path.isfile(json_file):
        return {}
    else:
        with open(json_file) as f:
            return json.load(f)


def get_gh_usernames():
    return {
        "bcolsson": "Bryan",
        "Delphine": "Delphine",
        "flodolo": "Flod",
        "peiying2": "Peiying",
    }


def get_phab_usernames():
    return {
        "bolsson": "Bryan",
        "delphine": "Delphine",
        "flod": "Flod",
    }


def write_json_data(json_data):
    json_file = get_json_file()
    with open(json_file, "w+") as f:
        f.write(json.dumps(json_data, indent=2, sort_keys=True))


def store_json_data(key, record, day=None, extend=False):
    json_data = get_json_data()
    if not day:
        day = datetime.today().strftime("%Y-%m-%d")
    if key not in json_data:
        json_data[key] = {}
    if extend:
        data = json_data[key].get(day, {})
        data.update(record)
        json_data[key][day] = data
    else:
        json_data[key][day] = record

    write_json_data(json_data)


def phab_query(method, data, after=None, **kwargs):
    phab_token, server = read_config("phab")
    server = server.rstrip("/")
    req = url_request.Request(
        f"{server}/{method}",
        method="POST",
        data=url_parse.urlencode(
            {
                "params": json.dumps(
                    {
                        **kwargs,
                        "__conduit__": {"token": phab_token},
                        "after": after,
                    }
                ),
                "output": "json",
                "__conduit__": True,
            }
        ).encode(),
    )

    with url_request.urlopen(req) as r:
        res = json.load(r)
    if res["error_code"] and res["error_info"]:
        raise Exception(res["error_info"])

    if res["result"]["cursor"]["after"] is not None:
        # print(f'Fetching new page (from {res["result"]["cursor"]["after"]})')
        phab_query(method, data, res["result"]["cursor"]["after"], **kwargs)

    if "results" in data:
        data["results"].extend(res["result"]["data"])
    else:
        data["results"] = res["result"]["data"]


def get_user_pr_collection(period_data, start_date):
    usernames = get_gh_usernames()
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
                period_data["repositories"].add(repo_name)
                count = contrib["contributions"]["totalCount"]
                total_reviewed += count
                period_data["pr_reviewed"][username][repo_name] = count
            period_data["pr_reviewed"][username]["total"] = total_reviewed

            # Get PR opened
            total_created = 0
            for contrib in json_data["pullRequestContributionsByRepository"]:
                repo_name = contrib["repository"]["nameWithOwner"]
                period_data["repositories"].add(repo_name)
                count = contrib["contributions"]["totalCount"]
                total_created += count
                period_data["pr_created"][username][repo_name] = count
            period_data["pr_created"][username]["total"] = total_created
        except Exception as e:
            print(e)


def get_pr_details(
    repos, usernames, start_date, pr_stats, end_date=None, single_repo=False
):
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
        number
        author {
            login
        }
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

    if end_date:
        query_prs = query_prs.replace(">=%START%", "%START%..%END%")

    start_query = start_date - timedelta(weeks=6)
    query_prs = query_prs.replace("%START%", start_query.strftime("%Y-%m-%d"))
    if end_date:
        query_prs = query_prs.replace("%END%", end_date.strftime("%Y-%m-%d"))

    for repo in repos:
        print(f"Requesting data for {repo}")
        query_pr_data(start_date, repo, usernames, query_prs, pr_stats, single_repo)


def query_pr_data(start_date, repo, usernames, query, pr_stats, single_repo, cursor=""):
    repo_query = query.replace("%REPO%", repo)
    if cursor != "":
        repo_query = repo_query.replace("%CURSOR%", f'after: "{cursor}"')
    else:
        repo_query = repo_query.replace("%CURSOR%", "")

    r = github_api_request(repo_query)
    r_data = r.json()["data"]["search"]
    for node in r_data["nodes"]:
        pr_author = node.get("author", {}).get("login", "")
        pr_date = datetime.strptime(node["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
        pr_number = node.get("number", None)
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

                review_time = review_date - pr_date
                if repo not in pr_stats["review_times"][author]:
                    pr_stats["review_times"][author][repo] = [
                        review_time.total_seconds()
                    ]
                else:
                    pr_stats["review_times"][author][repo].append(
                        review_time.total_seconds()
                    )

        if pr_author in usernames and pr_date >= start_date:
            if pr_author in pr_stats["pr_authored"]:
                pr_stats["pr_authored"][pr_author].add(pr_number)
            else:
                pr_stats["pr_authored"][pr_author] = {pr_number}

        # If I'm looking at a single repo, I want to store how long it took to
        # close any of the PRs.
        if single_repo and node.get("merged", False):
            close_date = datetime.strptime(node["closedAt"], "%Y-%m-%dT%H:%M:%SZ")
            close_time = close_date - pr_date
            if repo in pr_stats["pr_closed"]:
                pr_stats["pr_closed"][repo].append(close_time.total_seconds())
            else:
                pr_stats["pr_closed"][repo] = [close_time.total_seconds()]

    if r_data["pageInfo"]["hasNextPage"]:
        new_cursor = r_data["pageInfo"]["endCursor"]
        # print(f"  Requesting new page (from {new_cursor})")
        query_pr_data(
            start_date, repo, usernames, query, pr_stats, single_repo, new_cursor
        )

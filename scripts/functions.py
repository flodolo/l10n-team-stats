# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import configparser
import json
import os
import random
import re
import time
import urllib.parse

from datetime import date, datetime, time as dt_time, timedelta

import gspread
import requests
import urllib3

from github import Github
from jira import JIRA
from phab_cache import get_transactions, set_transactions


class InlineListEncoder(json.JSONEncoder):
    def encode(self, o):
        # First, encode using the parent class to respect indent and sort_keys.
        json_str = super().encode(o)
        # Define a regex pattern that matches arrays containing one or more nested arrays.
        pattern = re.compile(r"\[\s*((?:\[[^\[\]]+\](?:,\s*)?)+)\s*\]")

        def collapse(match):
            inner = match.group(1)
            # Replace newlines and extra whitespace inside the array with a single space.
            inner = re.sub(r"\s*\n\s*", " ", inner)
            return "[" + inner + "]"

        # Apply the regex substitution to collapse nested arrays.
        return pattern.sub(collapse, json_str)


def ymd(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid YYYY-MM-DD date: {value}")


def parse_arguments(
    repo=False,
    user=False,
    group=False,
):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start",
        "-s",
        type=ymd,
        help="Start date (YYYY-MM-DD, defaults to 1 week ago)",
    )
    parser.add_argument("--end", "-e", help="End date for analysis (YYYY-MM-DD)")
    parser.add_argument(
        "--verbose", "-v", help="Print list of revisions", action="store_true"
    )
    if repo:
        parser.add_argument(
            "--repo", "-r", help="Repository (e.g. mozilla/pontoon))", required=True
        )
    if group:
        parser.add_argument("--group", "-g", help="Group name on Phabricator")
    if user:
        parser.add_argument("--user", "-u", help="Username on GitHub")
    args = parser.parse_args()

    if not args.start:
        args.start = datetime.today() - timedelta(weeks=1)
    args.start = args.start.replace(hour=0, minute=0, second=0, microsecond=0)

    # By default, the period is 1 week (7 days) from the start date (or from
    # today, if not provided).
    if args.end:
        args.end = datetime.strptime(args.end, "%Y-%m-%d")
    else:
        args.end = args.start + timedelta(weeks=1)
    args.end = args.end.replace(hour=0, minute=0, second=0, microsecond=0)

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
    start_dt = datetime.combine(start_date, dt_time.min).replace(tzinfo=dt.tzinfo)
    end_dt = datetime.combine(end_date, dt_time.min).replace(tzinfo=dt.tzinfo)
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


def search_jira_issues(connection, query, changelog=False, fields="*all"):
    return connection.enhanced_search_issues(
        jql_str=query,
        maxResults=0,  # 0/False => fetch ALL pages internally
        fields=fields,  # comma-separated string works best
        expand="changelog" if changelog else None,
        # use_post=True can help if your JQL is long
    )


def get_json_file():
    return os.path.join(os.path.dirname(__file__), os.pardir, "data", "data.json")


def get_known_phab_diffs():
    filename = os.path.join(
        os.path.dirname(__file__), os.pardir, "data", "phab_diffs.json"
    )
    if not os.path.isfile(filename):
        return {}

    with open(filename) as f:
        return json.load(f)


def store_known_phab_diffs(diffs):
    filename = os.path.join(
        os.path.dirname(__file__), os.pardir, "data", "phab_diffs.json"
    )
    diffs["authored"].sort()
    diffs["reviewed"].sort()
    with open(filename, "w") as f:
        return json.dump(diffs, f, indent=2, sort_keys=True)


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
        f.write(json.dumps(json_data, cls=InlineListEncoder, indent=2, sort_keys=True))


def store_json_data(key, record, day=None, extend=False):
    json_data = get_json_data()
    if not day:
        day = datetime.today()
    day_str = day.strftime("%Y-%m-%d")
    if key not in json_data:
        json_data[key] = {}
    if extend:
        data = json_data[key].get(day_str, {})
        data.update(record)
        json_data[key][day_str] = data
    else:
        json_data[key][day_str] = record

    write_json_data(json_data)


def phab_search_revisions(search_constraints):
    revisions_response = {}
    phab_query(
        "differential.revision.search",
        revisions_response,
        constraints=search_constraints,
        order="newest",
    )

    return revisions_response.get("results", [])


def phab_diff_transactions(id, phid):
    # Fetch transactions related to the revision. Use local cache if available.
    transactions_response = get_transactions(id)
    if not transactions_response:
        transactions_response = {}
        print(f"Getting transactions for {id}...")
        phab_query(
            "transaction.search",
            transactions_response,
            objectIdentifier=phid,
        )
        set_transactions(id, transactions_response)
    else:
        print(f"Using cached transactions for {id}...")

    return transactions_response.get("results", [])


def phab_query(method: str, data: dict, after=None, **kwargs) -> dict:
    timeout = kwargs.pop("_timeout", 10)
    retries = kwargs.pop("_retries", 3)
    backoff = kwargs.pop("_backoff", 0.8)

    phab_token, server = read_config("phab")
    # Ensure no trailing slash or /api suffix
    server = server.rstrip("/").removesuffix("/api")
    url = f"{server}/api/{method}"

    results = data.get("results", [])
    cursor_after = after

    http = urllib3.PoolManager(
        timeout=urllib3.Timeout(total=timeout),
        retries=False,
        headers={
            "User-Agent": "phab-query/urllib3",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    while True:
        params_obj = dict(kwargs)
        params_obj["__conduit__"] = {"token": phab_token}
        if cursor_after is not None:
            params_obj["after"] = cursor_after

        payload = {
            "api.token": phab_token,
            "output": "json",
            "params": json.dumps(params_obj),
            "__conduit__": "true",
        }

        body = urllib.parse.urlencode(payload)

        attempt = 0
        while True:
            try:
                resp = http.request("POST", url, body=body, redirect=False)
                status = resp.status
                text = (resp.data or b"").decode("utf-8", errors="replace")

                if status in (301, 302, 303, 307, 308):
                    raise RuntimeError(
                        f"HTTP redirect {status} calling {url}. "
                        f"Location: {resp.headers.get('Location')}"
                    )

                if status == 429:
                    retry_after = resp.headers.get("Retry-After")
                    sleep_s = (
                        int(retry_after)
                        if retry_after and str(retry_after).isdigit()
                        else backoff * (2**attempt) + random.uniform(0, 0.5)
                    )
                    if attempt >= retries:
                        raise RuntimeError(
                            f"HTTP 429 Too Many Requests calling {url}\n"
                            f"Retry-After: {retry_after}\n"
                            f"Body (first 1000 chars):\n{text[:1000]}"
                        )
                    time.sleep(sleep_s)
                    attempt += 1
                    continue

                if not (200 <= status < 300):
                    raise RuntimeError(
                        f"HTTP {status} calling {url}\n"
                        f"Body (first 1000 chars):\n{text[:1000]}"
                    )

                try:
                    res = json.loads(text)
                except json.JSONDecodeError as e:
                    raise RuntimeError(
                        f"JSON decode error calling {url}: {e}\n"
                        f"Body (first 1000 chars):\n{text[:1000]}"
                    ) from e

                break
            except urllib3.exceptions.HTTPError as e:
                if attempt >= retries:
                    raise RuntimeError(
                        f"Network error after {retries + 1} attempts calling {url}: {e}"
                    ) from e
                time.sleep(backoff * (2**attempt) + random.uniform(0, 0.5))
                attempt += 1

        if res.get("error_code") or res.get("error_info"):
            raise RuntimeError(
                f"Conduit error {res.get('error_code')}: {res.get('error_info')}"
            )

        result = res.get("result") or {}
        results.extend(result.get("data") or [])

        cursor_after = (result.get("cursor") or {}).get("after")
        if not cursor_after:
            break

    data["results"] = results
    return data


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


def get_pr_details(repos, usernames, start_date, end_date, pr_stats, single_repo=False):
    query_prs = """
{
  search(
    first: 100
    query: "repo:%REPO% is:pr created:%START%..%END%"
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
        pr_author = (node.get("author") or {}).get("login", "")
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


def get_gsheet_object(sheet_name):
    config = read_config("gdocs")
    credentials = {
        "type": "service_account",
        "project_id": config["gspread_project_id"],
        "private_key_id": config["gspread_private_key_id"],
        "private_key": config["gspread_private_key"].replace("\\n", "\n"),
        "client_id": config["gspread_client_id"],
        "client_email": config["gspread_client_email"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": config["client_x509_cert_url"],
    }

    connection = gspread.service_account_from_dict(credentials)
    return connection.open_by_key(config[sheet_name])


def update_stats_sheet(sh, sheet_name, export):
    columns = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    num_columns = len(export[0])
    num_rows = len(export)
    wks = sh.worksheet(sheet_name)

    print(f"Updating sheet: {sheet_name}")

    # Autoresize doesn't seem to widen the columns enough. To work around it,
    # add spaces after each column header.
    export[0] = [f"{label}   " for label in export[0]]

    wks.update(export, "A1", value_input_option="USER_ENTERED")
    wks.format(
        f"A1:{columns[num_columns - 1]}1",
        {
            "backgroundColorStyle": {
                "rgbColor": {"red": 0.85, "green": 0.85, "blue": 0.85}
            },
            "textFormat": {"bold": True},
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "TOP",
            "wrapStrategy": "WRAP",
        },
    )

    data_sheet_id = wks._properties["sheetId"]
    body = {
        "requests": [
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": data_sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": num_columns,
                    }
                },
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": data_sheet_id,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": num_rows,
                    }
                },
            },
        ]
    }
    sh.batch_update(body)

    # Format as date the second column (minus header)
    # Define the formatting request using Google Sheets API
    body = {
        "requests": [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": data_sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": 999,
                        "startColumnIndex": 0,
                        "endColumnIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "DATE", "pattern": "yyyy-MM-dd"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            }
        ]
    }
    sh.batch_update(body)

    # Fetch sheet metadata to identify pivot tables
    requests = []
    meta = sh.fetch_sheet_metadata(
        params={
            "includeGridData": True,
            "fields": (
                "sheets(properties(sheetId,title),data(rowData(values(pivotTable))))"
            ),
        }
    )
    new_source_gridrange = {
        "sheetId": data_sheet_id,
        "startRowIndex": 0,
        "endRowIndex": num_rows,
        "startColumnIndex": 0,
        "endColumnIndex": num_columns,
    }
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        sheet_id = props.get("sheetId")

        if sheet_id == data_sheet_id:
            continue

        for grid in sheet.get("data", []):
            for r, row in enumerate(grid.get("rowData", []) or []):
                values = row.get("values") or []
                for c, cell in enumerate(values):
                    pivot = cell.get("pivotTable")
                    if not pivot:
                        continue

                    # Replace the pivot source with new data range
                    pivot["source"] = new_source_gridrange

                    requests.append(
                        {
                            "updateCells": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": r,
                                    "endRowIndex": r + 1,
                                    "startColumnIndex": c,
                                    "endColumnIndex": c + 1,
                                },
                                "rows": [{"values": [{"pivotTable": pivot}]}],
                                "fields": "pivotTable",
                            }
                        }
                    )
    if requests:
        sh.batch_update({"requests": requests})
        print(
            f"Updated {len(requests)} pivot table(s) to source Data!A1:{columns[num_columns - 1]}{num_rows}."
        )
    else:
        print("No pivot tables found outside the data sheet.")

    # Update spreadsheet title
    current_title = sh.title
    today = date.today().isoformat()

    new_title = re.sub(r"\(\d{4}-\d{2}-\d{2}\)", f"({today})", current_title)
    if new_title != current_title:
        sh.batch_update(
            {
                "requests": [
                    {
                        "updateSpreadsheetProperties": {
                            "properties": {"title": new_title},
                            "fields": "title",
                        }
                    }
                ]
            }
        )
        print(f"Spreadsheet renamed to: {new_title}")
    else:
        print("No date found to replace in spreadsheet title.")

#!/usr/bin/env python3

import argparse
import configparser
import datetime
import os
import urllib3
from github import Github
from jira import JIRA


def ymd(value):
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid YYYY-MM-DD date: {value}")


def parse_arguments(repo=False):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--since", "-s", type=ymd, help="Start date (defaults to 1 week ago)"
    )
    parser.add_argument(
        "--verbose", "-v", help="Print list of revisions", action="store_true"
    )
    if repo:
        parser.add_argument(
            "--repo", "-r", help="Repository (e.g. mozilla/pontoon))", required=True
        )
    args = parser.parse_args()

    if not args.since:
        args.since = datetime.datetime.today() - datetime.timedelta(weeks=1)
    args.since = args.since.replace(hour=0, minute=0, second=0, microsecond=0)

    return args


def read_config(key):
    # Read config file in the parent folder
    config_file = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
        "api_config.env",
    )
    config = configparser.ConfigParser()
    config.read(config_file)
    if key == "github":
        return config.get("KEYS", "GITHUB_TOKEN")

    if key == "jira":
        return (
            config.get("KEYS", "JIRA_EMAIL"),
            config.get("KEYS", "JIRA_TOKEN"),
            config.get("URLS", "JIRA_SERVER"),
        )


def format_time(interval):
    if interval < 3600:
        interval = round(interval / 60)
        return f"{interval} minutes"
    elif interval < 86400:
        interval = round(interval / 3600)
        return f"{interval} hours"
    else:
        interval = round(interval / 86400)
        return f"{interval} days"


def get_github_object():
    github_token = read_config(key="github")
    return Github(
        github_token,
        retry=urllib3.util.retry.Retry(
            total=10, status_forcelist=(500, 502, 504), backoff_factor=0.3
        ),
    )


def get_jira_object():
    jira_email, jira_token, jira_server = read_config(key="jira")
    return JIRA(
        basic_auth=(jira_email, jira_token),
        server=jira_server,
    )

#!/usr/bin/env python3

import argparse
import configparser
import datetime
import os


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

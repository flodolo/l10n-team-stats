#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
from functions import get_jira_object, search_jira_issues


def main():
    jira = get_jira_object()

    errors = []

    issues = search_jira_issues(
        jira,
        "project = 'l10n-vendor' AND status != Canceled AND createdDate >= 2025-01-01",
        changelog=True
    )

    for issue in issues:
        issue_id = issue.key
        if issue_id in ["L10NV-263"]:
            date_created = datetime.datetime.strptime(
                issue.fields.created, "%Y-%m-%dT%H:%M:%S.%f%z"
            ).strftime("%Y-%m-%d")

            print(f"Changes from issue: {issue.key} {issue.fields.summary}")
            print(f"Issue created on: {issue.fields.created}")
            print(
                f"Number of Changelog entries found: {issue.changelog.total}"
            )  # number of changelog entries (careful, each entry can have multiple field changes)

            for history in reversed(issue.changelog.histories):
                print(f"Author: {history.author}")  # person who did the change
                print(f"Timestamp: {history.created}")  # when did the change happen?
                print("\nListing all items that changed:")

                for item in history.items:
                    print(f"Field name: {item.field}")  # field to which the change happened
                    print(
                        f"Changed to: {item.toString}"
                    )  # new value, item.to might be better in some cases depending on your needs.
                    print(
                        f"Changed from: {item.fromString}"
                    )  # old value, item.from might be better in some cases depending on your needs.
                    print()
            print()


if __name__ == "__main__":
    main()

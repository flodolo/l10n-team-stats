#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import re
from functions import get_jira_object, search_jira_issues


def main():
    jira = get_jira_object()

    errors = []

    issues = search_jira_issues(
        jira,
        "project = 'l10n-requests' AND status != Canceled",
    )

    output = []

    for issue in issues:
        issue_id = issue.key
        date_created = datetime.datetime.strptime(
            issue.fields.created, "%Y-%m-%dT%H:%M:%S.%f%z"
        ).strftime("%Y-%m-%d")

        assignee = issue.fields.assignee.displayName if issue.fields.assignee else "-"
        components = "+".join([c.name for c in issue.fields.components])
        if components == "":
            errors.insert(0, f"{issue_id}: no component assigned")
        output.append(
            f"{issue.key},{date_created},{issue.fields.reporter},{issue.fields.reporter.emailAddress},{components},{assignee}"
        )

    output.append("Issue ID,Date,Reporter,Reporter Email,Components,Assignee")
    output.reverse()

    if errors:
        print("There are errors:")
        print("\n".join(errors))

    print("\n----CSV output----\n\n")
    print("\n".join(output))


if __name__ == "__main__":
    main()

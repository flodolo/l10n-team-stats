#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from functions import get_github_object
import csv

def main():
    repo = "mozilla/pontoon"

    g = get_github_object()
    print(f"Analysis of repository: {repo}\n")

    issues_data = []
    open_issues = g.search_issues(
        query=f"repo:{repo} is:issue is:open",
        sort="created",
        order="desc",
    )
    for issue in open_issues:
        labels = [label.name for label in issue.labels]
        label = ", ".join(labels) if len(labels) > 0 else "-"
        issues_data.append(
            [
                f'=HYPERLINK("{issue.html_url}", "{issue.number}")',
                issue.title,
                issue.body,
                label,
                issue.created_at.strftime("%Y-%m-%d"),
                issue.updated_at.strftime("%Y-%m-%d"),
            ]
        )

    with open("output.csv", "w", newline="", encoding="utf-8") as f:
        issues_data.insert(0, ["Issue","Title","Body","Labels","Created","Last Update"])
        writer = csv.writer(f, quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerows(issues_data)
        print("Content saved as output.csv")

if __name__ == "__main__":
    main()

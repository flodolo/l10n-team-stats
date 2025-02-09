#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import statistics
from functions import (
    parse_arguments,
    get_jira_object,
    search_jira_issues,
    store_json_data,
)


def store_date(issue_data, issue, field, dt):
    issue_id = issue.key
    if issue_id not in issue_data:
        issue_data[issue_id] = {
            "created": issue.fields.created,
            "deadline": issue.fields.customfield_10451,
        }

    issue_data[issue_id][field] = dt


def main():
    args = parse_arguments()
    since_date = args.start.strftime("%Y-%m-%d")

    jira = get_jira_object()

    # I need to check for issues whose status changed within the last week,
    # not just created.
    issues = search_jira_issues(
        jira,
        f"project = 'l10n-vendor' AND status != Canceled AND status CHANGED FROM 'BACKLOG' AFTER {since_date}",
        changelog=True,
    )

    issue_data = {}
    for issue in issues:
        for history in reversed(issue.changelog.histories):
            for item in history.items:
                # Ignore changes without a fieldId (e.g. parent change)
                if not hasattr(item, "fieldId"):
                    continue

                if item.fieldId == "status" and item.toString == "To Do":
                    store_date(issue_data, issue, "triaged", history.created)
                if item.fieldId == "status" and item.toString == "Vendor Delivery":
                    store_date(issue_data, issue, "delivered", history.created)
                if item.fieldId == "status" and item.toString == "Scheduled":
                    store_date(issue_data, issue, "scheduled", history.created)

    times = {
        "triage": [],
        "deliver": [],
        "deadline": [],
    }
    for issue, issue_details in issue_data.items():
        create_dt = datetime.datetime.strptime(
            issue_details["created"], "%Y-%m-%dT%H:%M:%S.%f%z"
        )
        triage_str = issue_details.get("triaged", issue_details.get("scheduled", None))
        if triage_str is not None:
            triage_dt = datetime.datetime.strptime(triage_str, "%Y-%m-%dT%H:%M:%S.%f%z")
            delta = triage_dt - create_dt
            issue_details["time_triage"] = round(delta.total_seconds() / 86400, 3)
            times["triage"].append(issue_details["time_triage"])

        deliver_str = issue_details.get("delivered", None)
        if deliver_str is not None:
            deliver_dt = datetime.datetime.strptime(
                deliver_str, "%Y-%m-%dT%H:%M:%S.%f%z"
            )
            delta = deliver_dt - create_dt
            issue_details["time_deliver"] = round(delta.total_seconds() / 86400, 3)
            times["deliver"].append(issue_details["time_deliver"])

            deadline_dt = datetime.datetime.strptime(
                issue_details["deadline"], "%Y-%m-%d"
            )
            # Add timezone, consider end of day
            deadline_dt = deadline_dt.replace(
                tzinfo=datetime.timezone.utc, hour=23, minute=59, second=59
            )
            delta = deliver_dt - deadline_dt
            issue_details["time_deadline"] = round(delta.total_seconds() / 86400, 3)
            times["deadline"].append(issue_details["time_deadline"])

    record = {}
    for type, type_data in times.items():
        if type_data:
            avg = round(statistics.mean(type_data), 2)
            print(f"Average time to {type}: {avg}")
            record[type] = avg
        else:
            record[type] = 0

    store_json_data(since_date, "jira-vendor-stats", record)


if __name__ == "__main__":
    main()

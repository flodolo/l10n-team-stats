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
        # If deadline is not defined, assume 1 week from filing
        if issue.fields.duedate:
            deadline = issue.fields.duedate
        else:
            create_dt = datetime.datetime.strptime(
                issue.fields.created, "%Y-%m-%dT%H:%M:%S.%f%z"
            )
            deadline = (create_dt + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            print(f"Missing deadline for {issue_id}: assuming {deadline}")
        issue_data[issue_id] = {
            "created": issue.fields.created,
            "deadline": deadline,
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
        f"project = 'l10n-requests' AND status != Blocked AND status CHANGED FROM 'BACKLOG' AFTER '{since_date}'",
        changelog=True,
    )

    ignored_issues = ["LR-45"]
    issue_data = {}
    for issue in issues:
        print(f"Checking issue {issue.key}")
        if issue.key in ignored_issues:
            continue
        for history in reversed(issue.changelog.histories):
            for item in history.items:
                # Ignore changes without a fieldId (e.g. parent change)
                if not hasattr(item, "fieldId"):
                    continue

                # Don't reset fields if an issue was reopened
                if (
                    item.fieldId == "status"
                    and item.toString == "In Progress"
                    and not issue_data.get(issue.key, {}).get("triaged", None)
                ):
                    store_date(issue_data, issue, "triaged", history.created)
                if (
                    item.fieldId == "status"
                    and item.toString == "Done"
                    and not issue_data.get(issue.key, {}).get("completed", None)
                ):
                    store_date(issue_data, issue, "completed", history.created)

    times = {
        "triage": [],
        "complete": [],
        "deadline": [],
    }
    num_triaged = 0
    num_completed = 0
    for issue, issue_details in issue_data.items():
        create_dt = datetime.datetime.strptime(
            issue_details["created"], "%Y-%m-%dT%H:%M:%S.%f%z"
        )
        triage_str = issue_details.get("triaged", issue_details.get("completed", None))
        if triage_str is not None:
            triage_dt = datetime.datetime.strptime(triage_str, "%Y-%m-%dT%H:%M:%S.%f%z")
            delta = triage_dt - create_dt
            issue_details["time_triage"] = round(delta.total_seconds() / 86400, 3)
            times["triage"].append(issue_details["time_triage"])
            num_triaged += 1

        complete_str = issue_details.get("completed", None)
        if complete_str is not None:
            complete_dt = datetime.datetime.strptime(
                complete_str, "%Y-%m-%dT%H:%M:%S.%f%z"
            )
            delta = complete_dt - create_dt
            issue_details["time_complete"] = round(delta.total_seconds() / 86400, 3)
            times["complete"].append(issue_details["time_complete"])
            num_completed += 1

            deadline_dt = datetime.datetime.strptime(
                issue_details["deadline"], "%Y-%m-%d"
            )
            # Add timezone, consider end of day
            deadline_dt = deadline_dt.replace(
                tzinfo=datetime.timezone.utc, hour=23, minute=59, second=59
            )
            delta = complete_dt - deadline_dt
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
    record["num_triaged"] = num_triaged
    record["num_completed"] = num_completed

    store_json_data("jira-request-stats", record)


if __name__ == "__main__":
    main()

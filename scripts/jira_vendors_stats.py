#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import statistics

from functions import (
    check_date_interval,
    get_jira_object,
    parse_arguments,
    search_jira_issues,
    store_json_data,
)


def store_date(issue_data, issue, field, dt):
    issue_id = issue.key
    # If deadline is not defined, assume 1 week from filing.
    if issue.fields.customfield_10451:
        deadline = issue.fields.customfield_10451
    else:
        create_dt = datetime.datetime.strptime(
            issue.fields.created, "%Y-%m-%dT%H:%M:%S.%f%z"
        )
        deadline = (create_dt + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        create_str = create_dt.strftime("%Y-%m-%d")
        print(f"  - Missing deadline, assuming {deadline} (created on {create_str})")
    if issue_id not in issue_data:
        issue_data[issue_id] = {
            "created": issue.fields.created,
            "deadline": deadline,
        }

    issue_data[issue_id][field] = dt


def main():
    args = parse_arguments()
    start_date = args.start
    str_start_date = start_date.strftime("%Y-%m-%d")
    end_date = args.end
    str_end_date = end_date.strftime("%Y-%m-%d")
    print(f"Checking issues changed between {str_start_date} and {str_end_date}")

    jira = get_jira_object()

    # I need to check for issues whose status changed within the last week,
    # not just created.
    issues = search_jira_issues(
        jira,
        f"project = 'l10n-vendor' AND status != Canceled AND status CHANGED DURING ('{str_start_date}', '{str_end_date}')",
        changelog=True,
    )

    ignored_issues = []
    issue_data = {}
    for issue in issues:
        print(f"Checking issue {issue.key}")
        if issue.key in ignored_issues:
            continue
        triaged_issue = False
        for history in reversed(issue.changelog.histories):
            for item in history.items:
                # Ignore changes without a fieldId (e.g. issue's parent change).
                if not hasattr(item, "fieldId"):
                    continue
                # Don't reset fields if an issue was reopened.
                if (
                    item.fieldId == "status"
                    and item.fromString == "Backlog"
                    and item.toString == "To Do"
                    and not triaged_issue
                ):
                    triaged_issue = True
                    if check_date_interval(start_date, end_date, history.created):
                        store_date(issue_data, issue, "triaged", history.created)
                    else:
                        print(
                            f"  - Ignored triage date out of bounds {history.created}"
                        )

                if (
                    item.fieldId == "status"
                    and item.toString == "Scheduled"
                    and not issue_data.get(issue.key, {}).get("scheduled", None)
                ):
                    # If the issue moved from Backlog to Scheduled without going
                    # trough To Do, store the scheduled date as triaged.
                    if check_date_interval(start_date, end_date, history.created):
                        if item.fromString == "Backlog" and not triaged_issue:
                            store_date(issue_data, issue, "triaged", history.created)
                        store_date(issue_data, issue, "scheduled", history.created)
                    else:
                        print(
                            f"  - Ignored scheduled date out of bounds {history.created}"
                        )

                if (
                    item.fieldId == "status"
                    and item.toString == "Vendor Delivery"
                    and not issue_data.get(issue.key, {}).get("delivered", None)
                ):
                    if check_date_interval(start_date, end_date, history.created):
                        store_date(issue_data, issue, "delivered", history.created)
                    else:
                        print(
                            f"  - Ignored delivered date out of bounds {history.created}"
                        )

    times = {
        "triage": [],
        "deliver": [],
        "deadline": [],
    }
    triaged = []
    delivered = []
    for issue, issue_details in issue_data.items():
        create_dt = datetime.datetime.strptime(
            issue_details["created"], "%Y-%m-%dT%H:%M:%S.%f%z"
        )
        triage_str = issue_details.get("triaged", None)
        print(f"Issue: {issue}")
        print(f" - Created on {create_dt.strftime('%Y-%m-%d %H:%M:%S %z')}")
        if triage_str is not None:
            triage_dt = datetime.datetime.strptime(triage_str, "%Y-%m-%dT%H:%M:%S.%f%z")
            delta = triage_dt - create_dt
            time_triage_str = round(delta.total_seconds() / 86400, 3)
            issue_details["time_triage"] = time_triage_str
            times["triage"].append(issue_details["time_triage"])
            triaged.append(issue)
            print(
                f" - Triaged on {triage_dt.strftime('%Y-%m-%d %H:%M:%S %z')}. Time to triage: {time_triage_str}mdays"
            )

        deliver_str = issue_details.get("delivered", None)
        if deliver_str is not None:
            deliver_dt = datetime.datetime.strptime(
                deliver_str, "%Y-%m-%dT%H:%M:%S.%f%z"
            )
            delta = deliver_dt - create_dt
            time_deliver_str = round(delta.total_seconds() / 86400, 3)
            issue_details["time_deliver"] = time_deliver_str
            times["deliver"].append(issue_details["time_deliver"])
            delivered.append(issue)
            print(
                f" - Delivered on {deliver_dt.strftime('%Y-%m-%d %H:%M:%S %z')}. Time to close: {time_deliver_str} days"
            )

            deadline_dt = datetime.datetime.strptime(
                issue_details["deadline"], "%Y-%m-%d"
            )
            # Add timezone, assume end of day.
            deadline_dt = deadline_dt.replace(
                tzinfo=datetime.timezone.utc, hour=23, minute=59, second=59
            )
            delta = deliver_dt - deadline_dt
            deadline_perf_str = round(delta.total_seconds() / 86400, 3)
            issue_details["time_deadline"] = deadline_perf_str
            times["deadline"].append(issue_details["time_deadline"])
            print(
                f" - Performance against deadline ({deadline_dt.strftime('%Y-%m-%d %H:%M:%S %z')}): {deadline_perf_str} days"
            )

    record = {}
    for type, type_data in times.items():
        if type_data:
            avg = round(statistics.mean(type_data), 2)
            print(f"Average time to {type}: {avg}")
            record[type] = avg
        else:
            record[type] = 0
    triaged.sort()
    delivered.sort()
    record["triaged"] = ", ".join(triaged)
    record["num_triaged"] = len(triaged)
    record["delivered"] = ", ".join(delivered)
    record["num_delivered"] = len(delivered)

    store_json_data("jira-vendor-stats", record, day=end_date)


if __name__ == "__main__":
    main()

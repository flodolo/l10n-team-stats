#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import gspread
from functions import (
    get_json_data,
    read_config,
)

columns = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def update_sheet(sh, sheet_name, export):
    num_columns = len(export[0])
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

    sheetId = wks._properties["sheetId"]
    body = {
        "requests": [
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheetId,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": num_columns,
                    }
                },
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheetId,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": len(export),
                    }
                },
            },
        ]
    }
    sh.batch_update(body)

    # Format as date the first column (minus header)
    # Define the formatting request using Google Sheets API
    body = {
        "requests": [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheetId,
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

    range_name = f"{sheet_name[4:]}_data"
    # Update or define named range
    try:
        named_ranges = sh.list_named_ranges()
        named_range_id = None
        for range in named_ranges:
            if range["name"] == range_name:
                named_range_id = range["namedRangeId"]
                break
        # Create a new one if missing
        if not named_range_id:
            end_cell = f"{columns[num_columns - 1]}{len(export)}"
            wks.define_named_range(f"A1:{end_cell}", range_name)
        else:
            body = {
                "requests": [
                    {
                        "updateNamedRange": {
                            "namedRange": {
                                "namedRangeId": named_range_id,
                                "name": range_name,
                                "range": {
                                    "sheetId": sheetId,
                                    "startRowIndex": 0,
                                    "endRowIndex": len(export),
                                    "startColumnIndex": 0,
                                    "endColumnIndex": num_columns,
                                },
                            },
                            "fields": "range",
                        }
                    }
                ]
            }
            sh.batch_update(body)
    except gspread.exceptions.APIError as e:
        print(f"Error removing named range {range_name}: {e}")


def main():
    data = get_json_data()
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
    sh = connection.open_by_key(config["spreadsheet_key"])

    # Export Phabricator group data
    export = []
    export.append(
        [
            "Date",
            "Android Reviewed",
            "Android Avg Review Time (h)",
            "Android Distribution",
            "Fluent Reviewed",
            "Fluent Avg Review Time (h)",
            "Fluent Distribution",
        ]
    )

    def get_distribution(day_data, group):
        total = 0
        distribution = {}
        details = day_data.get(group, {}).get("details", {})
        if not details:
            return ""

        for user, user_data in details.items():
            distribution[user] = len(user_data)
            total += len(user_data)
        distribution = {k: round(v * 100 / total, 2) for k, v in distribution.items()}

        return ", ".join([f"{user}: {perc}%" for user, perc in distribution.items()])

    for day, day_data in data["phab-groups"].items():
        _row = [
            day,
            day_data.get("android-l10n-reviewers", {}).get("total_reviews", 0),
            day_data.get("android-l10n-reviewers", {}).get("average_review_time", ""),
            get_distribution(day_data, "android-l10n-reviewers"),
            day_data.get("fluent-reviewers", {}).get("total_reviews", 0),
            day_data.get("fluent-reviewers", {}).get("average_review_time", ""),
            get_distribution(day_data, "fluent-reviewers"),
        ]
        export.append(_row)
    update_sheet(sh, "raw_phab_groups", export)

    # Export Jira LSP (vendor) stats
    export = []
    export.append(
        [
            "Date",
            "Avg triage (d)",
            "Avg deliver (d)",
            "Avg perf against deadline (d)",
            "Triaged",
            "Delivered",
        ]
    )
    for day, day_data in data["jira-vendor-stats"].items():
        _row = [
            day,
            day_data["triage"],
            day_data["deliver"],
            day_data["deadline"],
            (
                f"({day_data['num_triaged']}): {day_data['triaged']}"
                if day_data["triaged"]
                else ""
            ),
            (
                f"({day_data['num_delivered']}): {day_data['delivered']}"
                if day_data["delivered"]
                else ""
            ),
        ]
        export.append(_row)
    update_sheet(sh, "raw_vendor_stats", export)

    # Export Jira requests stats
    export = []
    export.append(
        [
            "Date",
            "Avg triage (d)",
            "Avg complete (d)",
            "Avg perf against deadline (d)",
            "Triaged",
            "Completed",
        ]
    )
    for day, day_data in data["jira-request-stats"].items():
        _row = [
            day,
            day_data["triage"],
            day_data["complete"],
            day_data["deadline"],
            (
                f"({day_data['num_triaged']}): {day_data['triaged']}"
                if day_data["triaged"]
                else ""
            ),
            (
                f"({day_data['num_completed']}): {day_data['completed']}"
                if day_data["completed"]
                else ""
            ),
        ]
        export.append(_row)
    update_sheet(sh, "raw_request_stats", export)

    # Export Pontoon PR data
    export = []
    export.append(
        [
            "Date",
            "New",
            "Closed",
            "Average Time\nto Close (h)",
            "Currently\nOpen",
            "Average\nAge (h)",
        ]
    )
    for day, day_data in data["pontoon-prs"].items():
        _row = [
            day,
            day_data["opened"],
            day_data["closed"],
            day_data["avg-time-to-close"],
            day_data["open"],
            day_data["avg-age-open"],
        ]
        export.append(_row)
    update_sheet(sh, "raw_pontoon_prs", export)

    # Export Pontoon issues
    export = []
    export.append(
        [
            "Date",
            "New",
            "Closed",
            "Average Time\nto Close (h)",
            "P1",
            "P2",
            "P3",
            "P4",
            "P5",
            "Untriaged",
            "Total Open",
        ]
    )
    for day, day_data in data["pontoon-issues"].items():
        _row = [
            day,
            day_data["opened"],
            day_data["closed"],
            day_data["avg-time-to-close"],
            day_data["P1"],
            day_data["P2"],
            day_data["P3"],
            day_data["P4"],
            day_data["P5"],
            day_data["Untriaged"],
            day_data["Total"],
        ]
        export.append(_row)
    update_sheet(sh, "raw_pontoon_issues", export)

    # Export Jira issues
    export = []
    export.append(
        [
            "Date",
            "Blocked",
            "Backlog",
            "In Progress",
            "New",
            "Closed issues",
        ]
    )
    for day, day_data in data["jira-issues"].items():
        _row = [
            day,
            day_data["blocked"],
            day_data["backlog"],
            day_data["in-progress"],
            day_data["created"],
            day_data["closed"],
        ]
        export.append(_row)
    update_sheet(sh, "raw_jira_issues", export)

    # Export EPM Review
    export = []
    export.append(
        [
            "Date",
            "Phabricator\nAuthored",
            "Phabricator\nReviewed",
            "Phabricator\nAvg Review\nTime (h)",
            "GitHub\nReviewed",
            "GitHub\nAvg Review\nTime (h)",
            "GitHub\nPR Opened",
            "Active\nRepositories",
        ]
    )
    for day, day_data in data["epm-reviews"].items():
        _row = [
            day,
            day_data["phab-authored"],
            day_data["phab-reviewed"],
            day_data.get("phab-avg-time-to-review", ""),
            day_data["github-reviews"],
            day_data["github-avg-time-to-review"],
            day_data["github-pr-created"],
            day_data["github-repositories"],
        ]
        export.append(_row)
    update_sheet(sh, "raw_epm_reviews", export)


if __name__ == "__main__":
    main()

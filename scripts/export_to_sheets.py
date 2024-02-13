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


def format_columns(sh, sheet_name, export):
    num_columns = len(export[0])
    wks = sh.worksheet(sheet_name)

    print(f"Updating sheet: {sheet_name}")

    # Autoresize doesn't seem to widen the columns enough. To work around it,
    # add spaces after each column header.
    export[0] = [f"{label}   " for label in export[0]]

    wks.update(export, "A1")
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
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheetId,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": 1,
                        "endIndex": num_columns,
                    }
                },
            }
        ]
    }
    sh.batch_update(body)


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
    format_columns(sh, "Pontoon PRs", export)

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
    format_columns(sh, "Pontoon Issues", export)

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
    format_columns(sh, "Jira Issues (EPM)", export)

    # Export EPM Review
    export = []
    export.append(
        [
            "Date",
            "Phabricator\nAuthored",
            "Phabricator\nReviewed",
            "GitHub\nReviewed",
            "Avg Review\nTime (h)",
            "GitHub\nPR Opened",
            "Active\nRepositories",
        ]
    )
    for day, day_data in data["epm-reviews"].items():
        _row = [
            day,
            day_data["phab-authored"],
            day_data["phab-reviewed"],
            day_data["github-reviews"],
            day_data["github-avg-time-to-review"],
            day_data["github-pr-created"],
            day_data["github-repositories"],
        ]
        export.append(_row)
    format_columns(sh, "EPM Reviews", export)


if __name__ == "__main__":
    main()

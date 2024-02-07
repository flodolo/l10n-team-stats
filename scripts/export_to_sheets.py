#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import gspread
import json
from functions import (
    get_json_data,
    read_config,
)


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

    gc = gspread.service_account_from_dict(credentials)
    sh = gc.open_by_key(config["spreadsheet_key"])

    # Export Pontoon PR data
    export = []
    export.append(
        [
            "Date",
            "New PRs",
            "Closed PRs",
            "Average Time to Close",
            "Open PRs",
            "Average Age",
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
    wks = sh.worksheet("Pontoon PRs")
    wks.update(export, "A1")

    # Export Pontoon issues
    export = []
    export.append(
        [
            "Date",
            "New Issues",
            "Closed Issues",
            "Average Time to Close",
            "P1",
            "P2",
            "P3",
            "P4",
            "P5",
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
            day_data["Total"],
        ]
        export.append(_row)
    wks = sh.worksheet("Pontoon Issues")
    wks.update(export, "A1")

    # Export Jira issues
    export = []
    export.append(
        [
            "Date",
            "Issues in Backlog",
            "Issues In Progress",
            "New issues",
            "Closed issues",
        ]
    )
    for day, day_data in data["jira-issues"].items():
        _row = [
            day,
            day_data["backlog"],
            day_data["in-progress"],
            day_data["created"],
            day_data["closed"],
        ]
        export.append(_row)
    wks = sh.worksheet("Jira Issues (EPM)")
    wks.update(export, "A1")

    # Export EPM Review
    export = []
    export.append(
        [
            "Date",
            "Phab Authored",
            "Phab Reviewed",
            "GitHub Reviewed",
            "Avg Time to Review",
        ]
    )
    for day, day_data in data["epm-reviews"].items():
        _row = [
            day,
            day_data["phab-authored"],
            day_data["phab-reviewed"],
            day_data["github-reviews"],
            day_data["github-avg-time-to-review"],
        ]
        export.append(_row)
    wks = sh.worksheet("EPM Reviews")
    wks.update(export, "A1")


if __name__ == "__main__":
    main()

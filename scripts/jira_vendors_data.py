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
        f"project = 'l10n-vendor' AND status != Canceled AND issuetype != Epic",
    )

    output = []
    for issue in issues:
        issue_id = issue.key
        date_created = datetime.datetime.strptime(
            issue.fields.created, "%Y-%m-%dT%H:%M:%S.%f%z"
        ).strftime("%Y-%m-%d")

        # Try to extract numbers from the cost center field
        original_cc = issue.fields.customfield_10450
        if original_cc is None:
            original_cc = ""
        cc_numbers = re.findall(r"\d+", original_cc)
        cc = "-"
        if not cc_numbers:
            errors.insert(
                0, f"{issue_id}: cannot extract a cost center (value: {original_cc})"
            )
        elif len(cc_numbers) > 1:
            errors.insert(
                0,
                f"{issue_id}: multiple numbers in cost center, first was used (value: {original_cc})",
            )
        else:
            cc = cc_numbers[0]
            if len(cc) < 4:
                errors.insert(
                    0,
                    f"{issue_id}: extracted cost center ({cc}) is too short (value: {original_cc})",
                )
            elif len(cc) == 4:
                cc = f"{cc}0"
            cc = f"CC{cc}"

        invoiced = issue.fields.customfield_10814
        if invoiced is None:
            invoiced = 0

        assignee = issue.fields.assignee.displayName if issue.fields.assignee else "-"

        try:
            type = issue.fields.parent.fields.summary.strip()
        except AttributeError:
            errors.insert(0, f"{issue_id}: no parent (epic) available")
            type = "-"
        output.append(
            f"{issue.key},{date_created},{issue.fields.reporter},{cc},{type},{invoiced},{assignee}"
        )

    output.append("Issue ID,Date,Reporter,Cost Center,Epic,Invoiced,Assignee")
    output.reverse()

    if errors:
        print("There are errors:")
        print("\n".join(errors))

    print("\n----CSV output----\n\n")
    print("\n".join(output))


if __name__ == "__main__":
    main()

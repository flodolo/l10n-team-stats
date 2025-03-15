#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
This script retrieves differential revisions reviewed by a group in Phabricator,
calculates review times, and outputs the data in JSON format.
"""

import json
import statistics
import sys
from datetime import datetime
from functions import format_time, parse_arguments, phab_query


def get_revisions_review_data(group_members, results_data, search_constraints):
    """
    Retrieves differential revisions based on given constraints,
    processes transactions to identify review events from group members,
    and updates results_data with relevant timestamps and reviewer info.

    Args:
        group_members (dict): Mapping of user PHIDs to usernames.
        results_data (dict): Dictionary to store processed revision data.
        search_constraints (dict): Constraints for querying revisions.
    """
    # Query revisions reviewed by the group.
    revisions_response = {}
    phab_query(
        "differential.revision.search",
        revisions_response,
        constraints=search_constraints,
        order="newest",
    )
    revisions = revisions_response.get("results", [])
    if not revisions:
        return

    # Sort revisions by creation date.
    revisions = sorted(revisions, key=lambda rev: rev["fields"]["dateCreated"])

    for revision in revisions:
        revision_id = f"D{revision['id']}"
        # Fetch transactions related to the revision.
        transactions_response = {}
        phab_query(
            "transaction.search",
            transactions_response,
            objectIdentifier=revision["phid"],
        )

        # Process transactions to find review by a group member.
        transactions = transactions_response.get("results", [])
        reviewed = False
        for txn in transactions:
            if txn["type"] == "accept" and txn["authorPHID"] in group_members:
                reviewed = True
                revision_data = results_data.setdefault(revision_id, {})
                review_ts = txn["dateCreated"]
                revision_data["review_timestamp"] = review_ts
                revision_data["review_date"] = datetime.fromtimestamp(
                    review_ts
                ).strftime("%Y-%m-%d %H:%M")
                revision_data["reviewer"] = group_members[txn["authorPHID"]]
                # Once we've found the first valid review, we can break.
                break

        # If there was no review yet, ignore this diff.
        if not reviewed:
            continue

        create_ts = revision["fields"]["dateCreated"]
        revision_data["create_timestamp"] = create_ts
        revision_data["create_date"] = datetime.fromtimestamp(create_ts).strftime(
            "%Y-%m-%d %H:%M"
        )
        revision_data["title"] = f"{revision_id}: {revision['fields']['title']}"

        # If review_timestamp is set, calculate the time difference.
        if "review_timestamp" in revision_data:
            time_diff = (
                revision_data["review_timestamp"] - revision_data["create_timestamp"]
            )
            revision_data["time_to_review_h"] = round(time_diff / 3600, 2)
            revision_data["time_to_review"] = format_time(time_diff)


def main():
    args = parse_arguments(group=True, end_date=True)
    # Convert start/end dates to a Unix timestamp.
    since_timestamp = int(args.start.timestamp())
    end_timestamp = int(args.end.timestamp())

    # Retrieve group details by searching for the group (project) by name.
    group_query = {"query": args.group}
    group_response = {}
    phab_query(
        "project.search",
        group_response,
        constraints=group_query,
        attachments={"members": True},
    )
    if not group_response.get("results"):
        sys.exit(f"Group {args.group} not found.")

    group_info = group_response["results"][0]
    group_phid = group_info["phid"]
    # Extract the PHIDs of group members.
    group_member_phids = [
        member["phid"] for member in group_info["attachments"]["members"]["members"]
    ]

    # Retrieve detailed user data for the group members.
    user_query = {"phids": group_member_phids}
    user_response = {}
    phab_query("user.search", user_response, constraints=user_query)

    # Map user PHIDs to their usernames.
    group_members = {
        user["phid"]: user["fields"]["username"]
        for user in user_response.get("results", [])
    }

    revisions_data = {}
    revision_search_constraints = {
        "reviewerPHIDs": [group_phid],
        "createdStart": since_timestamp,
        "createdEnd": end_timestamp,
    }
    get_revisions_review_data(
        group_members, revisions_data, revision_search_constraints
    )

    stats = {}
    all_stats = []
    for rev_data in revisions_data.values():
        if rev_data["reviewer"] not in stats:
            stats[rev_data["reviewer"]] = [rev_data["time_to_review_h"]]
        else:
            stats[rev_data["reviewer"]].append(rev_data["time_to_review_h"])
        all_stats.append(rev_data["time_to_review_h"])

    print(
        f"Revisions between {args.start.strftime('%Y-%m-%d')} and {args.end.strftime('%Y-%m-%d')}"
    )
    print(
        f"Average time to review (h) for {args.group} ({len(all_stats)}): {round(statistics.mean(all_stats), 2)}"
    )
    for user, user_stats in stats.items():
        print(
            f"{user} ({len(user_stats)}, {round(len(user_stats) / len(all_stats) * 100, 2)}%): average (h) {round(statistics.mean(user_stats), 2)}"
        )


if __name__ == "__main__":
    main()

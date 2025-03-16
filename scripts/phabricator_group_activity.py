#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
This script retrieves differential revisions reviewed by a group in Phabricator,
calculates review times, and outputs the data in JSON format.
"""

import statistics
import sys
from datetime import datetime
from functions import (
    format_time,
    get_phab_usernames,
    parse_arguments,
    phab_query,
    store_json_data,
)


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
    print("Getting revisions for group...")
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
        print(f"Getting transactions for {revision_id}...")
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

    # TODO: start remove
    from datetime import timedelta
    args.end = args.start + timedelta(days=7)
    args.end = args.end.replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    end_timestamp = int(args.end.timestamp())
    # TODO: end remove

    if args.group:
        groups = [args.group]
    else:
        # Check all relevant groups
        groups = ["android-l10n-reviewers", "fluent-reviewers"]

    stats = {}
    l10n_users = get_phab_usernames().keys()
    for group in groups:
        # Retrieve group details by searching for the group (project) by name.
        group_query = {"query": group}
        group_response = {}
        print(f"\nGetting members of group {group}...")
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
        print("Getting info on members...")
        phab_query("user.search", user_response, constraints=user_query)

        # Map user PHIDs to their usernames and exclude users that are not part
        # of the l10n team.
        group_members = {
            user["phid"]: user["fields"]["username"]
            for user in user_response.get("results", [])
            if user["fields"]["username"] in l10n_users
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

        group_stats = {}
        all_reviews = []
        for rev_data in revisions_data.values():
            if rev_data["reviewer"] not in group_stats:
                group_stats[rev_data["reviewer"]] = [rev_data["time_to_review_h"]]
            else:
                group_stats[rev_data["reviewer"]].append(rev_data["time_to_review_h"])
            all_reviews.append(rev_data["time_to_review_h"])

        if group_stats:
            stats[group] = {
                "details": group_stats,
            }

    print(
        f"Revisions between {args.start.strftime('%Y-%m-%d')} and {args.end.strftime('%Y-%m-%d')}"
    )
    for group, group_data in stats.items():
        all_reviews = [
            rev_time for values in group_data["details"].values() for rev_time in values
        ]
        group_data["total_reviews"] = len(all_reviews)
        group_data["average_review_time"] = round(statistics.mean(all_reviews), 2)
        print(
            f"Average time to review (h) for {group} ({group_data['total_reviews']}): {group_data['average_review_time']}"
        )
        for user, user_stats in group_data["details"].items():
            perc = round(len(user_stats) / len(all_reviews) * 100, 2)
            print(
                f"{user} ({len(user_stats)}, {perc}%): average (h) {round(statistics.mean(user_stats), 2)}"
            )

    store_json_data("phab_groups", stats)


if __name__ == "__main__":
    main()

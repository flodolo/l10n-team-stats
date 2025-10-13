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
    get_known_phab_diffs,
    get_phab_usernames,
    parse_arguments,
    phab_diff_transactions,
    phab_query,
    phab_search_revisions,
    store_json_data,
    store_known_phab_diffs,
)


def get_revisions_review_data(
    group_members,
    results_data,
    group_phid,
    start_timestamp,
    end_timestamp,
    known_phab_diffs,
):
    # Query revisions for the group.
    print("Getting revisions created within the date range...")
    search_constraints = {
        "reviewerPHIDs": [group_phid],
        "createdStart": start_timestamp,
        "createdEnd": end_timestamp,
    }
    created_revisions = phab_search_revisions(search_constraints)

    print("Getting revisions modified within the date range...")
    search_constraints = {
        "reviewerPHIDs": [group_phid],
        "modifiedStart": start_timestamp,
        "modifiedEnd": end_timestamp,
    }
    modified_revisions = phab_search_revisions(search_constraints)

    # Remove duplicates.
    unique_revisions = {d["id"]: d for d in created_revisions + modified_revisions}
    revisions = list(unique_revisions.values())
    if not revisions:
        return

    # Sort revisions by creation date.
    revisions = sorted(revisions, key=lambda rev: rev["fields"]["dateCreated"])
    for revision in revisions:
        revision_id = f"D{revision['id']}"

        # Ignore diff that has been already authored or reviewed
        if revision_id in known_phab_diffs.get("type", []):
            print(f"Skipping known diff {revision_id} for type {type}")
            continue

        # Process transactions to find review by a group member.
        transactions = phab_diff_transactions(revision_id, revision["phid"])
        reviewed = False
        revision_data = {}
        review_request_timestamp = None
        for txn in transactions:
            # The review has to happen within the range.
            if (
                txn["type"] == "accept"
                and txn["authorPHID"] in group_members
                and (start_timestamp <= txn["dateCreated"] <= end_timestamp)
                and not reviewed
            ):
                reviewed = True
                revision_data = results_data.setdefault(revision_id, {})
                review_ts = txn["dateCreated"]
                revision_data["review_timestamp"] = review_ts
                revision_data["review_date"] = datetime.fromtimestamp(
                    review_ts
                ).strftime("%Y-%m-%d %H:%M")
                revision_data["reviewer"] = group_members[txn["authorPHID"]]
                known_phab_diffs["reviewed"].append(revision_id)

            # Store also when the review was requested.
            if txn["type"] == "reviewers":
                operations = txn["fields"].get("operations", [])
                try:
                    op = operations[0]
                    if (
                        op.get("operation", "") == "add"
                        and op.get("phid", "") == group_phid
                    ):
                        review_request_timestamp = txn["dateCreated"]
                except Exception as e:
                    print(e)
                    pass

        # If there was no review yet, ignore this diff.
        if not reviewed:
            continue

        create_ts = revision["fields"]["dateCreated"]
        revision_data["create_timestamp"] = create_ts
        revision_data["review_request_timestamp"] = review_request_timestamp
        revision_data["create_date"] = datetime.fromtimestamp(create_ts).strftime(
            "%Y-%m-%d %H:%M"
        )
        revision_data["title"] = f"{revision_id}: {revision['fields']['title']}"

        # Fall back to creation date if there is no review request timestamp.
        review_request = revision_data.get("review_request_timestamp", create_ts)
        time_diff = revision_data["review_timestamp"] - review_request
        revision_data["time_to_review_h"] = round(time_diff / 3600, 2)
        revision_data["time_to_review"] = format_time(time_diff)


def main():
    args = parse_arguments(group=True)
    # Convert start/end dates to a Unix timestamp.
    start_timestamp = int(args.start.timestamp())
    end_date = args.end
    end_timestamp = int(end_date.timestamp())

    if args.group:
        groups = [args.group]
    else:
        # Check all relevant groups.
        groups = ["android-l10n-reviewers", "fluent-reviewers"]

    print(
        f"Revisions between {args.start.strftime('%Y-%m-%d')} and {args.end.strftime('%Y-%m-%d')}"
    )

    stats = {}
    l10n_users = get_phab_usernames().keys()
    known_phab_diffs = get_known_phab_diffs()
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
        get_revisions_review_data(
            group_members,
            revisions_data,
            group_phid,
            start_timestamp,
            end_timestamp,
            known_phab_diffs,
        )

        group_stats = {}
        all_reviews = []
        for rev_id, rev_data in revisions_data.items():
            if rev_data["reviewer"] not in group_stats:
                group_stats[rev_data["reviewer"]] = [
                    (rev_id, rev_data["time_to_review_h"])
                ]
            else:
                group_stats[rev_data["reviewer"]].append(
                    (rev_id, rev_data["time_to_review_h"])
                )
            all_reviews.append(rev_data["time_to_review_h"])

        if group_stats:
            stats[group] = {
                "details": group_stats,
            }

    for group, group_stats in stats.items():
        all_reviews = [
            rev_time
            for values in group_stats["details"].values()
            for _, rev_time in values
        ]
        num_reviews = len(all_reviews)
        group_stats["total_reviews"] = num_reviews
        group_stats["average_review_time"] = round(statistics.mean(all_reviews), 2)
        print(
            f"Average time to review (h) for {group} ({group_stats['total_reviews']}): {group_stats['average_review_time']}"
        )
        for user, user_stats in group_stats["details"].items():
            user_reviews = [rev_time for _, rev_time in user_stats]
            num_user_reviews = len(user_stats)
            perc = round(num_user_reviews / num_reviews * 100, 2)
            print(
                f"{user} ({num_user_reviews}, {perc}%): average (h) {round(statistics.mean(user_reviews), 2)}"
            )

    store_json_data("phab-groups", stats, day=end_date)
    store_known_phab_diffs(known_phab_diffs)


if __name__ == "__main__":
    main()

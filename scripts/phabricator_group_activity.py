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
    get_known_phab_group_diffs,
    get_phab_usernames,
    parse_arguments,
    phab_diff_transactions,
    phab_query,
    phab_search_revisions,
    store_json_data,
)
from phab_cache import get_group, set_group


def get_revisions_review_data(
    group_members,
    results_data,
    group_phid,
    start_timestamp,
    end_timestamp,
    known_diffs,
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

        need_first_review = revision_id not in known_diffs["first_reviewed"]
        need_approval = revision_id not in known_diffs["approved"]

        if not need_first_review and not need_approval:
            print(f"Skipping already fully recorded diff {revision_id}")
            continue

        transactions = phab_diff_transactions(revision_id, revision["phid"])

        first_review_ts = None
        first_review_reviewer = None
        approve_ts = None
        approve_reviewer = None
        review_request_timestamp = None

        for txn in transactions:
            # Track when the review was requested by the group.
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

            if (
                txn["type"] in ("accept", "request-changes")
                and txn["authorPHID"] in group_members
                and (start_timestamp <= txn["dateCreated"] <= end_timestamp)
            ):
                if need_first_review and first_review_ts is None:
                    first_review_ts = txn["dateCreated"]
                    first_review_reviewer = group_members[txn["authorPHID"]]

                if need_approval and txn["type"] == "accept" and approve_ts is None:
                    approve_ts = txn["dateCreated"]
                    approve_reviewer = group_members[txn["authorPHID"]]

        if first_review_ts is None and approve_ts is None:
            continue

        create_ts = revision["fields"]["dateCreated"]
        review_request = review_request_timestamp or create_ts
        title = f"{revision_id}: {revision['fields']['title']}"
        create_date = datetime.fromtimestamp(create_ts).strftime("%Y-%m-%d %H:%M")

        revision_data = results_data.setdefault(
            revision_id,
            {
                "create_timestamp": create_ts,
                "create_date": create_date,
                "title": title,
                "review_request_timestamp": review_request,
            },
        )

        if first_review_ts is not None:
            time_diff = first_review_ts - review_request
            revision_data["first_review"] = {
                "timestamp": first_review_ts,
                "date": datetime.fromtimestamp(first_review_ts).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "reviewer": first_review_reviewer,
                "time_to_review_h": round(time_diff / 3600, 2),
                "time_to_review": format_time(time_diff),
            }

        if approve_ts is not None:
            time_diff = approve_ts - review_request
            revision_data["approval"] = {
                "timestamp": approve_ts,
                "date": datetime.fromtimestamp(approve_ts).strftime("%Y-%m-%d %H:%M"),
                "reviewer": approve_reviewer,
                "time_to_approve_h": round(time_diff / 3600, 2),
                "time_to_approve": format_time(time_diff),
            }


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
    known_diffs = get_known_phab_group_diffs()
    for group in groups:
        cached = get_group(group)
        if cached:
            print(f"\nUsing cached info for group {group}...")
            group_phid = cached["phid"]
            group_members = cached["members"]
        else:
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
            group_member_phids = [
                member["phid"]
                for member in group_info["attachments"]["members"]["members"]
            ]

            user_query = {"phids": group_member_phids}
            user_response = {}
            print("Getting info on members...")
            phab_query("user.search", user_response, constraints=user_query)

            group_members = {
                user["phid"]: user["fields"]["username"]
                for user in user_response.get("results", [])
                if user["fields"]["username"] in l10n_users
            }
            set_group(group, {"phid": group_phid, "members": group_members})

        revisions_data = {}
        get_revisions_review_data(
            group_members,
            revisions_data,
            group_phid,
            start_timestamp,
            end_timestamp,
            known_diffs,
        )

        # Aggregate per-reviewer stats.
        group_stats = {}
        for rev_id, rev_data in revisions_data.items():
            if "first_review" in rev_data:
                reviewer = rev_data["first_review"]["reviewer"]
                entry = group_stats.setdefault(
                    reviewer, {"first_reviews": [], "approvals": []}
                )
                entry["first_reviews"].append(
                    (rev_id, rev_data["first_review"]["time_to_review_h"])
                )
            if "approval" in rev_data:
                reviewer = rev_data["approval"]["reviewer"]
                entry = group_stats.setdefault(
                    reviewer, {"first_reviews": [], "approvals": []}
                )
                entry["approvals"].append(
                    (rev_id, rev_data["approval"]["time_to_approve_h"])
                )

        if group_stats:
            stats[group] = {"details": group_stats}

    for group, group_stats in stats.items():
        all_first_reviews = [
            t
            for u in group_stats["details"].values()
            for _, t in u["first_reviews"]
        ]
        all_approvals = [
            t
            for u in group_stats["details"].values()
            for _, t in u["approvals"]
        ]
        all_diff_ids = {
            rev_id
            for u in group_stats["details"].values()
            for rev_id, _ in u["first_reviews"] + u["approvals"]
        }

        group_stats["total_reviews"] = len(all_diff_ids)
        group_stats["total_first_reviews"] = len(all_first_reviews)
        group_stats["total_approvals"] = len(all_approvals)
        if all_first_reviews:
            group_stats["average_time_to_first_review"] = round(
                statistics.mean(all_first_reviews), 2
            )
        if all_approvals:
            group_stats["average_time_to_approve"] = round(
                statistics.mean(all_approvals), 2
            )

        print(
            f"1st reviews for {group} ({group_stats['total_first_reviews']}): "
            f"avg {group_stats.get('average_time_to_first_review', 'n/a')} h"
        )
        print(
            f"Approvals for {group} ({group_stats['total_approvals']}): "
            f"avg {group_stats.get('average_time_to_approve', 'n/a')} h"
        )
        for user, user_stats in group_stats["details"].items():
            n_first = len(user_stats["first_reviews"])
            n_approvals = len(user_stats["approvals"])
            avg_first = (
                round(statistics.mean([t for _, t in user_stats["first_reviews"]]), 2)
                if user_stats["first_reviews"]
                else "n/a"
            )
            avg_approve = (
                round(statistics.mean([t for _, t in user_stats["approvals"]]), 2)
                if user_stats["approvals"]
                else "n/a"
            )
            print(
                f"  {user}: 1st reviews={n_first} (avg {avg_first} h), "
                f"approvals={n_approvals} (avg {avg_approve} h)"
            )

    store_json_data("phab-groups", stats, day=end_date)


if __name__ == "__main__":
    main()

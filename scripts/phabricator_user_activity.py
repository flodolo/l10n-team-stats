#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import statistics

from functions import (
    get_known_phab_user_diffs,
    get_phab_usernames,
    parse_arguments,
    phab_diff_transactions,
    phab_query,
    phab_search_revisions,
    store_json_data,
)
from phab_cache import get_user_phids as get_cached_user_phids, set_user_phids


def get_revisions(
    type, user, results_data, start_timestamp, end_timestamp, known_diffs
):
    username = user["user"]
    print(f"Searching revisions {type} by {username}...")

    print("Getting revisions created within the date range...")
    if type == "authored":
        search_constraints = {
            "authorPHIDs": [user["phid"]],
            "createdStart": start_timestamp,
            "createdEnd": end_timestamp,
        }
    else:
        search_constraints = {
            "reviewerPHIDs": [user["phid"]],
            "createdStart": start_timestamp,
            "createdEnd": end_timestamp,
        }
    created_revisions = phab_search_revisions(search_constraints)

    print("Getting revisions modified within the date range...")
    if type == "authored":
        search_constraints = {
            "authorPHIDs": [user["phid"]],
            "modifiedStart": start_timestamp,
            "modifiedEnd": end_timestamp,
        }
    else:
        search_constraints = {
            "reviewerPHIDs": [user["phid"]],
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
    revisions = sorted(revisions, key=lambda d: d["fields"]["dateCreated"])
    for revision in revisions:
        revision_id = f"D{revision['id']}"

        if revision_id in known_diffs.get(type, set()):
            print(f"Skipping already recorded diff {revision_id} for type {type}")
            continue

        reviewed = False
        review_ts = None
        if type == "reviewed":
            # Process transactions to find review by the user.
            transactions = phab_diff_transactions(revision_id, revision["phid"])
            for txn in transactions:
                # For groups it's possible to look when the review was
                # requested. For individual users that's not reliable, as the
                # request might happen as part of a group.
                # The review has to happen within the range.
                if (
                    txn["type"] in ("accept", "request-changes")
                    and txn["authorPHID"] == user["phid"]
                    and (start_timestamp <= txn["dateCreated"] <= end_timestamp)
                ):
                    reviewed = True
                    review_ts = txn["dateCreated"]
                    break

        # If looking at reviews and there was no review yet, ignore this diff.
        if type == "reviewed" and not reviewed:
            continue

        date_created = datetime.datetime.fromtimestamp(
            revision["fields"]["dateCreated"], datetime.UTC
        )
        if username not in results_data:
            results_data[username] = {}
        if type == "authored":
            print(
                f"{revision_id} {date_created.strftime('%Y-%m-%d')} {revision['fields']['title']}"
            )
            if type not in results_data[username]:
                results_data[username][type] = [revision_id]
            else:
                results_data[username][type].append(revision_id)
        else:
            time_diff = review_ts - revision["fields"]["dateCreated"]
            time_to_review_h = round(time_diff / 3600, 2)
            print(
                f"{revision_id} {date_created.strftime('%Y-%m-%d')} {revision['fields']['title']} (review hours: {time_to_review_h})"
            )
            if type not in results_data[username]:
                results_data[username][type] = [(revision_id, time_to_review_h)]
            else:
                results_data[username][type].append((revision_id, time_to_review_h))


def get_user_phids():
    cached = get_cached_user_phids()
    if cached:
        print("Using cached user details...")
        return cached

    constraints = {
        "usernames": list(get_phab_usernames().keys()),
    }
    user_data = {}
    print("Getting user details...")
    phab_query("user.search", user_data, constraints=constraints)
    users = []
    for u in user_data["results"]:
        users.append(
            {
                "user": u["fields"]["username"],
                "name": u["fields"]["realName"],
                "phid": u["phid"],
            }
        )
    set_user_phids(users)
    return users


def main():
    args = parse_arguments()
    # Convert start/end dates to a Unix timestamp.
    start_timestamp = int(args.start.timestamp())
    end_date = args.end
    end_timestamp = int(end_date.timestamp())

    print(
        f"Revisions between {args.start.strftime('%Y-%m-%d')} and {args.end.strftime('%Y-%m-%d')}"
    )
    users = get_user_phids()
    known_diffs = get_known_phab_user_diffs()
    phab_data = {}
    for user in users:
        get_revisions(
            "authored", user, phab_data, start_timestamp, end_timestamp, known_diffs
        )
        get_revisions(
            "reviewed", user, phab_data, start_timestamp, end_timestamp, known_diffs
        )

    stats = {
        "phab-authored": 0,
        "phab-reviewed": 0,
        "phab-details": phab_data,
    }

    str_start_date = args.start.strftime("%Y-%m-%d")
    end_date = args.end
    str_end_date = end_date.strftime("%Y-%m-%d")

    total_authored = 0
    all_reviews = []
    for user, user_data in phab_data.items():
        print(f"\n\nActivity for {user} between {str_start_date} and {str_end_date}")
        authored = len(user_data.get("authored", []))
        reviewed = len(user_data.get("reviewed", []))
        print(f"Total authored: {authored}")
        print(f"Total reviewed: {reviewed}")
        user_reviews = [rev_time for _, rev_time in user_data.get("reviewed", [])]
        all_reviews += user_reviews
        total_authored += authored
        avg_review_time = round(statistics.mean(user_reviews), 2) if user_reviews else 0
        print(f"Average time to review: {avg_review_time}")

        stats["phab-authored"] += authored
        stats["phab-reviewed"] += reviewed

    print(f"\n\n-----\nTotal authored: {total_authored}")
    print(f"Total reviewed: {len(all_reviews)}")
    # Only store average review time if there actually are reviews.
    if all_reviews:
        avg_review = round(statistics.mean(all_reviews), 2)
        print(f"Average time to review: {avg_review}")
        stats["phab-avg-time-to-review"] = avg_review
    store_json_data("epm-reviews", stats, extend=True, day=end_date)


if __name__ == "__main__":
    main()

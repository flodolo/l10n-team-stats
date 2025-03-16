#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
from collections import defaultdict
from functions import get_phab_usernames, parse_arguments, phab_query, store_json_data


def get_revisions(type, user, data, constraints):
    revisions_response = {}
    print(f"Searching revisions {type} by {user}...")
    phab_query(
        "differential.revision.search",
        revisions_response,
        constraints=constraints,
        order="newest",
    )

    revisions = revisions_response.get("results", [])
    if not revisions:
        return

    revisions = sorted(revisions, key=lambda d: d["fields"]["dateCreated"])

    for revision in revisions:
        revision_id = f"D{revision['id']}"
        fields = revision["fields"]
        date_created = datetime.datetime.fromtimestamp(
            fields["dateCreated"], datetime.UTC
        )
        key = date_created.strftime("%Y-%m")
        if type not in data[user][key]:
            data[user][key][type] = []
        rev = f"D{revision_id} {date_created.strftime('%Y-%m-%d')} {fields['title']}"
        data[user][key][type].append(rev)


def print_revisions(data, stats, start_date, verbose):
    rev_details = {}
    stats["phab-authored"] = 0
    stats["phab-reviewed"] = 0
    for user, user_data in data.items():
        rev_details[user] = {
            "authored": [],
            "reviewed": [],
        }
        print(f"\n\nActivity for {user} since {start_date}")
        authored = 0
        reviewed = 0
        print("\nDetails (authored, reviewed):")
        periods = list(user_data.keys())
        periods.sort()
        for period in periods:
            period_data = user_data[period]
            print(
                f"{period}: {len(period_data['authored'])}, {len(period_data['reviewed'])}"
            )
            authored += len(period_data["authored"])
            reviewed += len(period_data["reviewed"])
            rev_details[user]["authored"].extend(period_data["authored"])
            rev_details[user]["reviewed"].extend(period_data["reviewed"])

        print(f"\nTotal authored: {authored}")
        print(f"Total reviewed: {reviewed}")

        stats["phab-authored"] += authored
        stats["phab-reviewed"] += reviewed

    if verbose:
        for user, user_data in rev_details.items():
            print(f"\n----\nDetailed data for {user}")
            for type, type_data in user_data.items():
                print(f"\nList of {type} revisions ({len(type_data)}):")
                for rev in type_data:
                    print(f"  {rev}")


def get_user_phids():
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

    return users


def recursivedict():
    return defaultdict(recursivedict)


def main():
    args = parse_arguments(end_date=True)
    # Convert start/end dates to a Unix timestamp.
    start_timestamp = int(args.start.timestamp())
    end_timestamp = int(args.end.timestamp())

    print(
        f"Revisions between {args.start.strftime('%Y-%m-%d')} and {args.end.strftime('%Y-%m-%d')}"
    )
    users = get_user_phids()
    phab_data = recursivedict()
    for u in users:
        get_revisions(
            "authored",
            u["user"],
            phab_data,
            dict(
                authorPHIDs=[u["phid"]],
                createdStart=start_timestamp,
                createdEnd=end_timestamp,
            ),
        )
        get_revisions(
            "reviewed",
            u["user"],
            phab_data,
            dict(
                reviewerPHIDs=[u["phid"]],
                createdStart=start_timestamp,
                createdEnd=end_timestamp,
            ),
        )

    stats = {}
    print_revisions(phab_data, stats, args.start.strftime("%Y-%m-%d"), args.verbose)
    store_json_data("epm-reviews", stats, extend=True)


if __name__ == "__main__":
    main()

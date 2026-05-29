#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import statistics

from functions import get_json_data, write_json_data


def main():
    data = get_json_data()

    # Recalculate totals and averages for phab-groups straight from the per-diff
    # details, so manually editing the details (e.g. removing a diff) propagates
    # to the derived fields. Two historical schemas exist: the legacy one stores
    # each person's reviews as a flat list of [diff_id, time] pairs and a single
    # average_review_time; the current one splits them into first_reviews/
    # approvals with separate totals and averages.
    for day_data in data["phab-groups"].values():
        for group_data in day_data.values():
            details = group_data["details"].values()
            if all(isinstance(person, list) for person in details):
                all_reviews = [time for person in details for _, time in person]
                group_data["total_reviews"] = len(all_reviews)
                if all_reviews:
                    group_data["average_review_time"] = round(
                        statistics.mean(all_reviews), 2
                    )
                continue
            all_first_reviews = [
                time for person in details for _, time in person["first_reviews"]
            ]
            all_approvals = [
                time for person in details for _, time in person["approvals"]
            ]
            all_diff_ids = {
                diff_id
                for person in details
                for diff_id, _ in person["first_reviews"] + person["approvals"]
            }
            group_data["total_reviews"] = len(all_diff_ids)
            group_data["total_first_reviews"] = len(all_first_reviews)
            group_data["total_approvals"] = len(all_approvals)
            if all_first_reviews:
                group_data["average_time_to_first_review"] = round(
                    statistics.mean(all_first_reviews), 2
                )
            if all_approvals:
                group_data["average_time_to_approve"] = round(
                    statistics.mean(all_approvals), 2
                )

    # Recalculate totals and averages for epm-reviews
    for day_data in data["epm-reviews"].values():
        all_reviews = [
            time
            for person_data in day_data["phab-details"].values()
            for _, time in person_data.get("reviewed", [])
        ]
        day_data["phab-reviewed"] = len(all_reviews)
        if all_reviews:
            day_data["phab-avg-time-to-review"] = round(
                statistics.mean(all_reviews), 2
            )

    write_json_data(data)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from functions import get_json_data, write_json_data


def main():
    data = get_json_data()

    # Recalculate averages for phab-groups
    for day_data in data["phab-groups"].values():
        for group_data in day_data.values():
            total = 0
            for person_data in group_data["details"].values():
                for _, time in person_data:
                    total += time
            group_data["average_review_time"] = round(
                total / group_data["total_reviews"], 2
            )

    # Recalculate averages for epm-reviews
    for day_data in data["epm-reviews"].values():
        total = 0
        for person_data in day_data["phab-details"].values():
            for _, time in person_data.get("reviewed", []):
                total += time
        if total > 0:
            day_data["phab-avg-time-to-review"] = round(
                total / day_data["phab-reviewed"], 2
            )

    write_json_data(data)


if __name__ == "__main__":
    main()

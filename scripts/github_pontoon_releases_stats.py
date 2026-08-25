#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import UTC

from functions import (
    get_github_object,
    parse_arguments,
    store_json_data,
)


def main():
    args = parse_arguments(dry=True)
    # Releases are timezone aware (UTC), while dates from arguments are not.
    start_date = args.start.replace(tzinfo=UTC)
    end_date = args.end.replace(tzinfo=UTC)
    str_start_date = args.start.strftime("%Y-%m-%d")
    str_end_date = args.end.strftime("%Y-%m-%d")
    repo_name = "mozilla/pontoon"

    g = get_github_object()
    repo = g.get_repo(repo_name)

    print(f"Analysis of repository: {repo_name}\n")

    releases = []
    total = 0
    for release in repo.get_releases():
        # Ignore drafts, they have no publication date.
        if release.draft or release.published_at is None:
            continue

        total += 1
        published_at = release.published_at
        if start_date <= published_at <= end_date:
            releases.append(release.tag_name)
            if args.verbose:
                print(f"Tag: {release.tag_name}")
                print(f"Published: {published_at.strftime('%Y-%m-%d %H:%M:%S')}")

    count = len(releases)
    print(
        f"Releases published between {str_start_date} and {str_end_date} ({count}): {', '.join(releases)}"
    )
    print(f"Total releases published: {total}")

    record = {
        "published": count,
        "tags": ", ".join(releases),
        "total": total,
    }

    if args.dry:
        print("Dry run: data is not stored.")
    else:
        store_json_data("pontoon-releases", record, day=args.end)


if __name__ == "__main__":
    main()

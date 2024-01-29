#!/usr/bin/env python3
import datetime
from collections import defaultdict
from functions import parse_arguments, phab_query


def get_revisions(type, user, data, constraints):
    revisions = {}
    phab_query(
        "differential.revision.search",
        revisions,
        constraints=constraints,
        order="newest",
    )

    revisions = revisions["results"]
    if not revisions:
        return

    revisions = sorted(revisions, key=lambda d: d["fields"]["dateCreated"])

    for revision in revisions:
        fields = revision["fields"]
        date_created = datetime.datetime.utcfromtimestamp(fields["dateCreated"])
        key = date_created.strftime("%Y-%m")
        if type not in data[user][key]:
            data[user][key][type] = []
        rev = (
            f'D{revision["id"]:5} {date_created.strftime("%Y-%m-%d")} {fields["title"]}'
        )
        data[user][key][type].append(rev)


def print_revisions(data, start_date, verbose):
    rev_details = {}
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

    if verbose:
        for user, user_data in rev_details.items():
            print(f"\n----\nDetailed data for {user}")
            for type, type_data in user_data.items():
                print(f"\nList of {type} revisions ({len(type_data)}):")
                for rev in type_data:
                    print(f"  {rev}")


def get_user_phids():
    constraints = {
        "usernames": [
            "bolsson",
            "flod",
            # "eemeli",
        ],
    }
    user_data = {}
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


def main():
    args = parse_arguments()
    since = int(args.since.timestamp())

    users = get_user_phids()

    recursivedict = lambda: defaultdict(recursivedict)
    data = recursivedict()
    for u in users:
        get_revisions(
            "authored",
            u["user"],
            data,
            dict(authorPHIDs=[u["phid"]], createdStart=since),
        )
        get_revisions(
            "reviewed",
            u["user"],
            data,
            dict(reviewerPHIDs=[u["phid"]], createdStart=since),
        )

    print_revisions(data, args.since.strftime("%Y-%m-%d"), args.verbose)


if __name__ == "__main__":
    main()

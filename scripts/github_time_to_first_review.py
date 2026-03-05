#! /usr/bin/env python3

from datetime import datetime

from functions import format_time, github_api_request, parse_arguments


QUERY_TEMPLATE = """
{
  search(
    first: 100
    query: "repo:%REPO% is:pr created:%START%..%END%"
    type: ISSUE
    %CURSOR%
  ) {
    nodes {
      ... on PullRequest {
        number
        title
        url
        author {
          login
        }
        createdAt
        reviews(first: 100) {
          nodes {
            author {
              login
            }
            submittedAt
            state
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def fetch_prs(repo, start_date, end_date, verbose=False):
    query = QUERY_TEMPLATE
    query = query.replace("%REPO%", repo)
    query = query.replace("%START%", start_date.strftime("%Y-%m-%d"))
    query = query.replace("%END%", end_date.strftime("%Y-%m-%d"))

    times = []
    prs_without_review = []

    def fetch_page(cursor=""):
        page_query = query.replace("%CURSOR%", f'after: "{cursor}"' if cursor else "")
        r = github_api_request(page_query)
        data = r.json()["data"]["search"]

        for node in data["nodes"]:
            pr_number = node["number"]
            pr_url = node.get("url", "")
            pr_author = (node.get("author") or {}).get("login", "")
            pr_created = datetime.strptime(node["createdAt"], "%Y-%m-%dT%H:%M:%SZ")

            # Find the earliest qualifying review (approved or changes requested)
            # by someone other than the PR author.
            first_review_time = None
            for review in node["reviews"]["nodes"]:
                if review["state"] not in ("APPROVED", "CHANGES_REQUESTED"):
                    continue
                reviewer = (review.get("author") or {}).get("login", "")
                if reviewer == pr_author:
                    continue
                review_dt = datetime.strptime(
                    review["submittedAt"], "%Y-%m-%dT%H:%M:%SZ"
                )
                if first_review_time is None or review_dt < first_review_time:
                    first_review_time = review_dt

            if first_review_time is not None:
                elapsed = (first_review_time - pr_created).total_seconds()
                times.append(elapsed)
                if verbose:
                    print(
                        f"  PR #{pr_number} ({pr_author}): {format_time(int(elapsed))} — {pr_url}"
                    )
            else:
                prs_without_review.append((pr_number, pr_author, pr_url))

        if data["pageInfo"]["hasNextPage"]:
            fetch_page(data["pageInfo"]["endCursor"])

    fetch_page()
    return times, prs_without_review


def main():
    args = parse_arguments(repo=True)
    repo = args.repo
    start_date = args.start
    end_date = args.end

    print(f"Repository: {repo}")
    print(
        f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )

    times, prs_without_review = fetch_prs(
        repo, start_date, end_date, verbose=args.verbose
    )

    total = len(times)
    if total > 0:
        avg = round(sum(times) / total)
        print(f"\nPRs with a first review: {total}")
        print(f"  Average time to first review: {format_time(avg)}")
        print(f"  Min time to first review:     {format_time(int(min(times)))}")
        print(f"  Max time to first review:     {format_time(int(max(times)))}")
    else:
        print("\nNo PRs with reviews found in this period.")

    if prs_without_review:
        print(f"\nPRs without a qualifying review: {len(prs_without_review)}")
        if args.verbose:
            for pr_number, pr_author, pr_url in prs_without_review:
                print(f"  PR #{pr_number} ({pr_author}): {pr_url}")


if __name__ == "__main__":
    main()

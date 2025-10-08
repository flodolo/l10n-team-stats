#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys

import requests


def main():
    projects = [
        "firefox-for-android",
        "firefox-for-ios",
        "firefox-monitor-website",
        "firefox-relay-website",
        "firefox",
        "mozilla-accounts",
        "mozilla-vpn-client",
    ]

    top15 = [
        "cs",
        "de",
        "es-AR",
        "es-ES",
        "es-MX",
        "fr",
        "hu",
        "id",
        "it",
        "ja",
        "nl",
        "pl",
        "pt-BR",
        "ru",
        "zh-CN",
    ]

    # Get stats from Pontoon
    locale_stats = {}
    for project in projects:
        url = f"https://pontoon.mozilla.org/api/v2/projects/{project}"
        page = 1
        try:
            while url:
                print(f"Reading data for project {project} (page {page})")
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                for locale_data in data.get("localizations", []):
                    locale = locale_data["locale"]["code"]
                    if locale not in top15:
                        continue
                    if locale not in locale_stats:
                        locale_stats[locale] = {
                            "projects": 0,
                            "missing": 0,
                            "approved": 0,
                            "pretranslated": 0,
                            "total": 0,
                            "completion": 0,
                        }
                    locale_stats[locale]["missing"] += locale_data["missing_strings"]
                    locale_stats[locale]["pretranslated"] += locale_data[
                        "pretranslated_strings"
                    ]
                    locale_stats[locale]["approved"] += locale_data["approved_strings"]
                    locale_stats[locale]["total"] += locale_data["total_strings"]
                    locale_stats[locale]["projects"] += 1
                # Get the next page URL
                url = data.get("next")
                page += 1
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            sys.exit()

    # Calculate average completion percentage
    total_strings = 0
    total_translations = 0
    for locale in top15:
        total_strings += locale_stats[locale]["total"]
        total_translations += locale_stats[locale]["approved"]
    avg_completion = round((total_translations / total_strings) * 100, 2)

    print(f"Average completion level for top 15 locales: {avg_completion}%")
    # Using French as a proxy for number of strings
    print(f"Number of strings (based on French): {locale_stats['fr']['total']}")
    print(f"Number of locales enabled in Pontoon: {len(locale_stats)}")


if __name__ == "__main__":
    main()

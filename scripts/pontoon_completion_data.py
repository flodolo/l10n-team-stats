#!/usr/bin/env python3

import json
from urllib.parse import quote as urlquote
from urllib.request import urlopen


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
    query = """
{
    projects {
        name
        slug
        localizations {
            locale {
                code
            },
            approvedStrings,
            missingStrings,
            pretranslatedStrings,
            totalStrings
        }
    }
}
"""
    locale_data = {}
    try:
        url = f"https://pontoon.mozilla.org/graphql?query={urlquote(query)}"
        response = urlopen(url)
        json_data = json.load(response)

        for project in json_data["data"]["projects"]:
            slug = project["slug"]
            if slug not in projects:
                continue

            for e in project["localizations"]:
                locale = e["locale"]["code"]
                if locale not in locale_data:
                    locale_data[locale] = {
                        "projects": 0,
                        "missing": 0,
                        "approved": 0,
                        "pretranslated": 0,
                        "total": 0,
                        "completion": 0,
                    }
                locale_data[locale]["missing"] += e["missingStrings"]
                locale_data[locale]["pretranslated"] += e["pretranslatedStrings"]
                locale_data[locale]["approved"] += e["approvedStrings"]
                locale_data[locale]["total"] += e["totalStrings"]
                locale_data[locale]["projects"] += 1
    except Exception as e:
        print(e)

    # Calculate average completion percentage
    total_strings = 0
    total_translations = 0
    for locale in top15:
        total_strings += locale_data[locale]["total"]
        total_translations += locale_data[locale]["approved"]
    avg_completion = round((total_translations / total_strings) * 100, 2)

    print(f"Average completion level for top 15 locales: {avg_completion}%")
    # Using French as a proxy for number of strings
    print(f"Number of strings (based on French): {locale_data['fr']['total']}")
    print(f"Number of locales enabled in Pontoon: {len(locale_data)}")


if __name__ == "__main__":
    main()

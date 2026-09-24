"""
Normalizes raw scraped phone numbers into a consistent, dialable
international format (e.g. "+1 555-123-4567") using the country each
lead was found in as a region hint. Falls back to the raw scraped text
for any number that can't be confidently parsed.
"""

import phonenumbers

import config


def normalize_phones(phones: list, country: str) -> list:
    region = config.COUNTRY_ISO2.get(country)
    normalized, seen = [], set()

    for raw in phones:
        formatted = raw
        try:
            parsed = phonenumbers.parse(raw, region)
            if phonenumbers.is_valid_number(parsed):
                formatted = phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
        except phonenumbers.NumberParseException:
            pass  # keep the raw text - better than dropping the lead's phone entirely

        if formatted not in seen:
            seen.add(formatted)
            normalized.append(formatted)

    return normalized

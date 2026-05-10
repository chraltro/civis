"""The 29 advanced economies in the Civis panel.

The country list is intentional and not user-configurable. Adding emerging
economies would change what the index *means*: it's a comparison frame for
"developed countries", not a global ranking.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    iso3: str
    iso2: str
    name: str


COUNTRIES: tuple[Country, ...] = (
    Country("AUS", "AU", "Australia"),
    Country("AUT", "AT", "Austria"),
    Country("BEL", "BE", "Belgium"),
    Country("CAN", "CA", "Canada"),
    Country("CZE", "CZ", "Czechia"),
    Country("DNK", "DK", "Denmark"),
    Country("EST", "EE", "Estonia"),
    Country("FIN", "FI", "Finland"),
    Country("FRA", "FR", "France"),
    Country("DEU", "DE", "Germany"),
    Country("HKG", "HK", "Hong Kong"),
    Country("ISL", "IS", "Iceland"),
    Country("ISR", "IL", "Israel"),
    Country("ITA", "IT", "Italy"),
    Country("JPN", "JP", "Japan"),
    Country("KOR", "KR", "Korea"),
    Country("LTU", "LT", "Lithuania"),
    Country("NLD", "NL", "Netherlands"),
    Country("NZL", "NZ", "New Zealand"),
    Country("NOR", "NO", "Norway"),
    Country("POL", "PL", "Poland"),
    Country("PRT", "PT", "Portugal"),
    Country("SGP", "SG", "Singapore"),
    Country("SVN", "SI", "Slovenia"),
    Country("ESP", "ES", "Spain"),
    Country("SWE", "SE", "Sweden"),
    Country("CHE", "CH", "Switzerland"),
    Country("GBR", "GB", "United Kingdom"),
    Country("USA", "US", "United States"),
)

ISO3_LIST: tuple[str, ...] = tuple(c.iso3 for c in COUNTRIES)
ISO3_TO_NAME: dict[str, str] = {c.iso3: c.name for c in COUNTRIES}

# Some OWID datasets use country names rather than ISO codes; map for normalization.
OWID_NAME_TO_ISO3: dict[str, str] = {
    "Australia": "AUS",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Canada": "CAN",
    "Czechia": "CZE",
    "Czech Republic": "CZE",
    "Denmark": "DNK",
    "Estonia": "EST",
    "Finland": "FIN",
    "France": "FRA",
    "Germany": "DEU",
    "Hong Kong": "HKG",
    "Iceland": "ISL",
    "Israel": "ISR",
    "Italy": "ITA",
    "Japan": "JPN",
    "Korea": "KOR",
    "South Korea": "KOR",
    "Korea, Rep.": "KOR",
    "Lithuania": "LTU",
    "Netherlands": "NLD",
    "New Zealand": "NZL",
    "Norway": "NOR",
    "Poland": "POL",
    "Portugal": "PRT",
    "Singapore": "SGP",
    "Slovenia": "SVN",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "CHE",
    "United Kingdom": "GBR",
    "United States": "USA",
}


def normalize_to_iso3(value: str) -> str | None:
    """Best-effort normalize a country name or code to ISO3."""
    if not value:
        return None
    v = value.strip()
    if len(v) == 3 and v.isupper():
        return v if v in ISO3_TO_NAME else None
    return OWID_NAME_TO_ISO3.get(v)

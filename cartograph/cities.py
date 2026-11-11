"""City hubs the public maps cover. Wikidata IDs pick the OpenStreetMap boundary."""

CITIES = [
    {"slug": "london", "name": "London", "region": "ON", "wikidata": ["Q92561"]},
    {"slug": "toronto", "name": "Toronto", "region": "ON", "wikidata": ["Q172"]},
    {"slug": "ottawa", "name": "Ottawa", "region": "ON", "wikidata": ["Q1930"]},
    {"slug": "hamilton", "name": "Hamilton", "region": "ON", "wikidata": ["Q133116"]},
    {"slug": "kitchener-waterloo", "name": "Kitchener-Waterloo", "region": "ON", "wikidata": ["Q200166", "Q639408"]},
    {"slug": "montreal", "name": "Montréal", "region": "QC", "wikidata": ["Q340"]},
    {"slug": "vancouver", "name": "Vancouver", "region": "BC", "wikidata": ["Q24639"]},
    {"slug": "calgary", "name": "Calgary", "region": "AB", "wikidata": ["Q36312"]},
]


def by_slug(slug: str) -> dict:
    for c in CITIES:
        if c["slug"] == slug:
            return c
    raise KeyError("Unknown city %r. Options: %s" % (slug, ", ".join(c["slug"] for c in CITIES)))

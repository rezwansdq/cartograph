"""Food places from OpenStreetMap via the Overpass API.

OpenStreetMap data is © OpenStreetMap contributors, available under the Open
Database License (ODbL). Maps built from it can be published as long as they
credit OpenStreetMap.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import Dict, List, Optional

import requests

from cartograph.geo import USER_AGENT

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
AMENITIES = ("restaurant", "cafe", "fast_food", "food_court", "ice_cream", "pub", "bar")

# Map OSM amenity values to the three map classes.
TYPE_BY_AMENITY = {
    "restaurant": "Restaurant",
    "food_court": "Restaurant",
    "cafe": "Cafe",
    "ice_cream": "Cafe",
    "fast_food": "Fast food",
    "pub": "Restaurant",
    "bar": "Restaurant",
}


def overpass_query(area_wikidata: List[str]) -> str:
    amenity_re = "|".join(AMENITIES)
    ids_re = "|".join(area_wikidata)
    return (
        "[out:json][timeout:180];"
        'area["boundary"="administrative"]["wikidata"~"^(%s)$"]->.a;'
        'nwr["amenity"~"^(%s)$"](area.a);'
        "out center tags;" % (ids_re, amenity_re)
    )


def fetch_elements(area_wikidata: List[str], retries: int = 3) -> List[Dict]:
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": overpass_query(area_wikidata)},
                headers={"User-Agent": USER_AGENT},
                timeout=240,
            )
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except (requests.RequestException, ValueError) as e:  # rate limits come back as HTML
            last_error = e
            time.sleep(30 * (attempt + 1))
    raise RuntimeError("Overpass request failed after %d tries: %s" % (retries, last_error))


def _coords(el: Dict) -> Optional[tuple]:
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    center = el.get("center")
    if center:
        return center["lat"], center["lon"]
    return None


def pretty_cuisine(raw: str) -> str:
    return raw.strip().replace("_", " ").capitalize()


def cuisines(tags: Dict) -> List[str]:
    return [pretty_cuisine(c) for c in (tags.get("cuisine") or "").split(";") if c.strip()]


_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


def open_late(opening_hours: Optional[str], cutoff_minutes: int = 23 * 60) -> Optional[bool]:
    """True if any time range runs to 11pm or later (or past midnight).

    Returns None when hours are unknown. This reads only the time ranges, not
    which days they apply to, so "late on at least one day" is what it means.
    """
    if not opening_hours:
        return None
    oh = opening_hours.strip()
    if "24/7" in oh:
        return True
    found = False
    for h1, m1, h2, m2 in _RANGE.findall(oh):
        found = True
        start = int(h1) * 60 + int(m1)
        end = int(h2) * 60 + int(m2)
        if end <= start or end >= cutoff_minutes:
            return True
    return False if found else None


def parse_places(elements: List[Dict]) -> List[Dict]:
    """Turn Overpass elements into flat rows. Chains are detected afterwards."""
    rows = []
    for el in elements:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        coords = _coords(el)
        if not name or coords is None:
            continue
        amenity = tags.get("amenity")
        rows.append(
            {
                "id": "%s/%s" % (el["type"], el["id"]),
                "name": name,
                "lat": round(coords[0], 6),
                "lon": round(coords[1], 6),
                "type": TYPE_BY_AMENITY.get(amenity, "Restaurant"),
                "amenity": amenity,
                "cuisines": cuisines(tags),
                "brand": tags.get("brand") or None,
                "has_brand_tag": bool(tags.get("brand") or tags.get("brand:wikidata")),
                "opening_hours": tags.get("opening_hours") or None,
                "late": open_late(tags.get("opening_hours")),
                "website": tags.get("website") or tags.get("contact:website") or None,
            }
        )
    return rows


def mark_chains(rows: List[Dict], min_locations: int = 3) -> List[Dict]:
    """A place is a chain if it has an OSM brand tag, or its name repeats min_locations+ times."""
    counts = Counter(r["name"].lower() for r in rows)
    for r in rows:
        r["chain"] = r["has_brand_tag"] or counts[r["name"].lower()] >= min_locations
        del r["has_brand_tag"]
    return rows

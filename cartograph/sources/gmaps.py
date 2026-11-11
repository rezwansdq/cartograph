"""Restaurants from Google Maps, via raw place data saved by google-maps-scraper.

The scraper (github.com/gosom/google-maps-scraper) is run with a small local
patch that writes each place's raw JSON to GMAPS_DUMP_DIR. We read those files
directly because Google no longer exposes a place-level price there; instead,
reviews carry a "price per person" answer such as "CA$20–30", and we take the
median of those.

Raw layout (index paths into the place array, as of November 2026):
    [11] name, [78] place id, [4][7] rating, [4][8] review count,
    [9][2] latitude, [9][3] longitude, [13] categories, [39] full address,
    [175] embedded reviews (price-per-person strings live in here).
"""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from cartograph.models import Restaurant

PRICE_RE = re.compile(r"^(?:CA)?\$(\d+)(?:\s*[–-]\s*(\d+)|\+)$")


def _get(arr: Any, *path: int) -> Any:
    for i in path:
        if not isinstance(arr, list) or i >= len(arr):
            return None
        arr = arr[i]
    return arr


def _strings(x: Any) -> Iterator[str]:
    if isinstance(x, list):
        for y in x:
            yield from _strings(y)
    elif isinstance(x, str):
        yield x


def price_midpoint(text: str) -> Optional[float]:
    """'CA$20–30' -> 25.0, 'CA$100+' -> 110.0, anything else -> None."""
    m = PRICE_RE.match(text.strip())
    if not m:
        return None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo + 20
    return (lo + hi) / 2.0


def review_prices(place: List) -> List[float]:
    """Every price-per-person answer found in the place's embedded reviews."""
    out = []
    for s in _strings(_get(place, 175)):
        v = price_midpoint(s)
        if v is not None:
            out.append(v)
    return out


def parse_place(raw: Any) -> Optional[Restaurant]:
    place = _get(raw, 6)
    if not isinstance(place, list):
        return None
    name = _get(place, 11)
    lat, lon = _get(place, 9, 2), _get(place, 9, 3)
    rating, count = _get(place, 4, 7), _get(place, 4, 8)
    if not name or lat is None or lon is None or rating is None:
        return None
    prices = review_prices(place)
    categories = [c for c in (_get(place, 13) or []) if isinstance(c, str)]
    return Restaurant(
        id=_get(place, 78) or "%s@%s,%s" % (name, lat, lon),
        name=name,
        lat=float(lat),
        lon=float(lon),
        rating=float(rating),
        review_count=int(count or 0),
        price_level=None,
        categories=categories,
        address=_get(place, 39) if isinstance(_get(place, 39), str) else None,
        source="google",
        price_per_person=statistics.median(prices) if prices else None,
        price_reports=len(prices),
    )


def load_raw_dir(raw_dir: Path) -> List[Restaurant]:
    """Parse every dumped place, keeping one entry per place id."""
    seen: Dict[str, Restaurant] = {}
    for f in sorted(raw_dir.glob("raw-*.json")):
        try:
            r = parse_place(json.loads(f.read_text(encoding="utf-8")))
        except (ValueError, TypeError):
            continue
        if r is not None:
            seen[r.id] = r
    return list(seen.values())


def fill_missing_prices(restaurants: List[Restaurant]) -> List[Restaurant]:
    """Give places with no price reports the median price of their main category.

    Falls back to the city-wide median. Filled-in prices keep price_reports == 0
    so the map can say they are estimates.
    """
    by_cat: Dict[str, List[float]] = defaultdict(list)
    for r in restaurants:
        if r.price_per_person is not None and r.categories:
            by_cat[r.categories[0]].append(r.price_per_person)
    known = [r.price_per_person for r in restaurants if r.price_per_person is not None]
    city_median = statistics.median(known) if known else None
    for r in restaurants:
        if r.price_per_person is None:
            cat = by_cat.get(r.categories[0]) if r.categories else None
            r.price_per_person = statistics.median(cat) if cat and len(cat) >= 3 else city_median
    return restaurants


def price_level_for(price_per_person: Optional[float]) -> Optional[int]:
    """Bucket a per-person price into $ to $$$$ for filtering."""
    if price_per_person is None:
        return None
    if price_per_person < 15:
        return 1
    if price_per_person < 30:
        return 2
    if price_per_person < 60:
        return 3
    return 4


FOOD_WORDS = (
    "restaurant", "cafe", "café", "coffee", "bakery", "bar", "pub", "grill", "pizza", "diner",
    "bistro", "eatery", "food", "takeout", "sushi", "shawarma", "deli", "bubble tea", "dessert",
    "ice cream", "brunch", "breakfast", "buffet", "steak", "noodle", "ramen", "pho", "taco",
    "burger", "sandwich", "wings", "chicken", "kitchen", "juice", "tea house", "gastropub",
)


def is_food_place(categories: List[str]) -> bool:
    cats = " | ".join(categories).lower()
    return any(w in cats for w in FOOD_WORDS)

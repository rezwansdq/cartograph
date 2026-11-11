"""Restaurants from the Yelp Open Dataset (a free download from yelp.com/dataset).

The business file is JSON Lines, one business per line, e.g.:

    {"business_id": "...", "name": "...", "address": "...", "city": "Philadelphia",
     "state": "PA", "latitude": 39.95, "longitude": -75.16, "stars": 4.5,
     "review_count": 120, "is_open": 1,
     "attributes": {"RestaurantsPriceRange2": "2", ...},
     "categories": "Restaurants, Pizza, Italian"}

The dataset is licensed for personal, educational and academic use. Check the
Dataset User Agreement that ships with it before publishing derived maps.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from cartograph.models import Restaurant


def _price_level(attributes: Optional[Dict]) -> Optional[int]:
    if not attributes:
        return None
    raw = attributes.get("RestaurantsPriceRange2")
    try:
        level = int(str(raw).strip().strip("'\""))
    except (TypeError, ValueError):
        return None
    return level if 1 <= level <= 4 else None


def _categories(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [c.strip() for c in raw.split(",") if c.strip()]


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def iter_businesses(path: Path) -> Iterator[Dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def is_open_restaurant(b: Dict) -> bool:
    return bool(b.get("is_open")) and "Restaurants" in _categories(b.get("categories"))


def parse_business(b: Dict) -> Optional[Restaurant]:
    if b.get("latitude") is None or b.get("longitude") is None:
        return None
    address = ", ".join(p for p in (b.get("address"), b.get("city"), b.get("state")) if p)
    return Restaurant(
        id=b["business_id"],
        name=b.get("name", ""),
        lat=float(b["latitude"]),
        lon=float(b["longitude"]),
        rating=float(b.get("stars") or 0),
        review_count=int(b.get("review_count") or 0),
        price_level=_price_level(b.get("attributes")),
        categories=[c for c in _categories(b.get("categories")) if c not in ("Restaurants", "Food")],
        address=address or None,
        source="yelp-open-dataset",
    )


def load_restaurants(path: Path, city: str, state: Optional[str] = None) -> List[Restaurant]:
    """Open restaurants in one city. City and state match case-insensitively."""
    want_city = _norm(city)
    want_state = _norm(state) if state else None
    out = []
    for b in iter_businesses(path):
        if _norm(b.get("city") or "") != want_city:
            continue
        if want_state and _norm(b.get("state") or "") != want_state:
            continue
        if not is_open_restaurant(b):
            continue
        r = parse_business(b)
        if r is not None:
            out.append(r)
    return out


def top_cities(path: Path, n: int = 25) -> List[Tuple[Tuple[str, str], int]]:
    """Cities with the most open restaurants, as ((city, state), count)."""
    counts: Counter = Counter()
    for b in iter_businesses(path):
        if is_open_restaurant(b):
            counts[((b.get("city") or "").strip(), (b.get("state") or "").strip())] += 1
    return counts.most_common(n)

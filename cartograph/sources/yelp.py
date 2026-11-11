"""Restaurants from the Yelp Fusion (Places) API.

Uses the official API rather than scraping yelp.com, which Yelp's terms forbid.
One search returns at most 50 results and offset + limit is capped at 240, so a
city is covered by tiling it into small circles and de-duplicating by id.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

from cartograph.geo import grid_points
from cartograph.models import Restaurant

SEARCH_URL = "https://api.yelp.com/v3/businesses/search"
PAGE_SIZE = 50
MAX_OFFSET_PLUS_LIMIT = 240


def _price_level(price: Optional[str]) -> Optional[int]:
    if not price:
        return None
    return len(price.strip())


def parse_business(b: Dict) -> Optional[Restaurant]:
    coords = b.get("coordinates") or {}
    if coords.get("latitude") is None or coords.get("longitude") is None:
        return None
    location = b.get("location") or {}
    return Restaurant(
        id=b["id"],
        name=b.get("name", ""),
        lat=float(coords["latitude"]),
        lon=float(coords["longitude"]),
        rating=float(b.get("rating") or 0),
        review_count=int(b.get("review_count") or 0),
        price_level=_price_level(b.get("price")),
        categories=[c.get("title", "") for c in b.get("categories") or []],
        url=b.get("url"),
        address=", ".join(location.get("display_address") or []) or None,
        source="yelp",
    )


def fetch_restaurants(
    lat: float,
    lon: float,
    radius_km: float = 8.0,
    step_km: float = 2.0,
    api_key: Optional[str] = None,
    raw_dir: Optional[Path] = None,
    pause_s: float = 0.25,
) -> List[Restaurant]:
    api_key = api_key or os.environ.get("YELP_API_KEY")
    if not api_key:
        raise RuntimeError("Set YELP_API_KEY in .env (see .env.example)")

    session = requests.Session()
    session.headers["Authorization"] = "Bearer " + api_key
    query_radius_m = int(step_km * 1000 * 0.75)
    seen: Dict[str, Restaurant] = {}

    for cell, (clat, clon) in enumerate(grid_points(lat, lon, radius_km, step_km)):
        offset = 0
        while offset + PAGE_SIZE <= MAX_OFFSET_PLUS_LIMIT:
            resp = session.get(
                SEARCH_URL,
                params={
                    "latitude": clat,
                    "longitude": clon,
                    "radius": query_radius_m,
                    "categories": "restaurants",
                    "limit": PAGE_SIZE,
                    "offset": offset,
                    "sort_by": "distance",
                },
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            if raw_dir is not None:
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / ("cell%03d_off%03d.json" % (cell, offset))).write_text(json.dumps(payload))

            businesses = payload.get("businesses") or []
            for b in businesses:
                r = parse_business(b)
                if r is not None:
                    seen[r.id] = r
            if len(businesses) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
            time.sleep(pause_s)
        time.sleep(pause_s)

    return list(seen.values())

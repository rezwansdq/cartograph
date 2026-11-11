from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import requests

USER_AGENT = "cartograph/0.1 (+https://map.rsadeqi.com)"


def geocode(place: str) -> Tuple[float, float]:
    """Look up a place name with OpenStreetMap Nominatim. Returns (lat, lon)."""
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError("Could not geocode %r" % place)
    return float(results[0]["lat"]), float(results[0]["lon"])


def grid_points(lat: float, lon: float, radius_km: float, step_km: float) -> Iterator[Tuple[float, float]]:
    """Yield grid cell centres covering a circle around (lat, lon)."""
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * math.cos(math.radians(lat))
    steps = int(math.ceil(radius_km / step_km))
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            dy, dx = i * step_km, j * step_km
            if math.hypot(dx, dy) <= radius_km + step_km / 2:
                yield lat + dy / km_per_deg_lat, lon + dx / km_per_deg_lon


def to_geojson(rows: List[Dict], meta: Optional[Dict] = None) -> Dict:
    features = []
    for row in rows:
        props = {k: v for k, v in row.items() if k not in ("lat", "lon")}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                "properties": props,
            }
        )
    fc = {"type": "FeatureCollection", "features": features}
    if meta:
        fc["meta"] = meta
    return fc


def write_geojson(path: Path, rows: List[Dict], meta: Optional[Dict] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_geojson(rows, meta), separators=(",", ":")))

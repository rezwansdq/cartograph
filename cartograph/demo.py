"""Synthetic restaurants so the map works before any API key is set up.

Every record is randomly generated and clearly marked as demo data.
"""

from __future__ import annotations

import random
from typing import List

from cartograph.models import Restaurant

CUISINES = ["Pizza", "Thai", "Burgers", "Sushi", "Indian", "Mexican", "Cafe", "Shawarma", "Vietnamese", "Italian"]


def demo_restaurants(lat: float, lon: float, n: int = 300, seed: int = 7) -> List[Restaurant]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        price = rng.choices([1, 2, 3, 4], weights=[35, 45, 15, 5])[0]
        rating = min(5.0, max(1.0, round(rng.gauss(3.9, 0.5) * 2) / 2))
        out.append(
            Restaurant(
                id="demo-%03d" % i,
                name="Demo %s #%d" % (rng.choice(CUISINES), i + 1),
                lat=lat + rng.gauss(0, 0.025),
                lon=lon + rng.gauss(0, 0.035),
                rating=rating,
                review_count=int(rng.lognormvariate(4, 1.1)),
                price_level=price,
                categories=[rng.choice(CUISINES)],
                source="demo",
            )
        )
    return out

"""Value score: how good a restaurant is for what it costs.

Two steps:

1. Bayesian average of the star rating. A 5.0 with 3 reviews should not beat a
   4.7 with 900 reviews, so each rating is pulled toward the city-wide mean in
   proportion to how few reviews it has:

       adjusted = (n * rating + m * mean) / (n + m)

   where n is the review count and m (`prior_reviews`) is how many "virtual"
   average reviews every place starts with.

2. Divide by cost. Price level is 1 ($) to 4 ($$$$). The exponent controls how
   hard cost is penalized: 0 ignores price, 1 makes a $$ place need double the
   rating of a $ place to tie.

       raw_value = adjusted / price_level ** price_exponent

The raw value is then turned into a 0 to 100 percentile within the dataset, so
a score of 90 means "better value than 90% of places in this city".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List

from cartograph.models import Restaurant


@dataclass
class ScoreConfig:
    prior_reviews: int = 50
    price_exponent: float = 0.5
    min_reviews: int = 5


def bayesian_rating(rating: float, n: int, prior_mean: float, m: int) -> float:
    if n + m == 0:
        return prior_mean
    return (n * rating + m * prior_mean) / (n + m)


def percentile_ranks(values: List[float]) -> List[float]:
    """Return a 0-100 percentile for each value. Ties share the same rank."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [100.0]
    ordered = sorted(values)
    out = []
    for v in values:
        below = _count_less(ordered, v)
        equal = _count_less_equal(ordered, v) - below
        out.append(100.0 * (below + (equal - 1) / 2.0) / (n - 1))
    return out


def _count_less(ordered: List[float], v: float) -> int:
    import bisect

    return bisect.bisect_left(ordered, v)


def _count_less_equal(ordered: List[float], v: float) -> int:
    import bisect

    return bisect.bisect_right(ordered, v)


def score_restaurants(
    restaurants: Iterable[Restaurant], config: ScoreConfig = ScoreConfig()
) -> List[Dict]:
    """Score every restaurant that has a price and enough reviews.

    Returns dicts (restaurant fields plus score fields), best first.
    """
    eligible = [
        r
        for r in restaurants
        if r.price_level is not None
        and 1 <= r.price_level <= 4
        and r.review_count >= config.min_reviews
    ]
    if not eligible:
        return []

    total_reviews = sum(r.review_count for r in eligible)
    prior_mean = sum(r.rating * r.review_count for r in eligible) / total_reviews

    rows = []
    for r in eligible:
        adjusted = bayesian_rating(r.rating, r.review_count, prior_mean, config.prior_reviews)
        raw_value = adjusted / (r.price_level ** config.price_exponent)
        row = asdict(r)
        row["adjusted_rating"] = round(adjusted, 3)
        row["raw_value"] = raw_value
        rows.append(row)

    for row, pct in zip(rows, percentile_ranks([row["raw_value"] for row in rows])):
        row["score"] = round(pct, 1)
        row["raw_value"] = round(row["raw_value"], 4)

    rows.sort(key=lambda row: row["raw_value"], reverse=True)
    return rows

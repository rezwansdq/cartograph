from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Restaurant:
    id: str
    name: str
    lat: float
    lon: float
    rating: float  # 1 to 5 stars
    review_count: int
    price_level: Optional[int]  # 1 ($) to 4 ($$$$); None when the source has no price
    categories: List[str] = field(default_factory=list)
    url: Optional[str] = None
    address: Optional[str] = None
    source: str = "unknown"
    # Typical spend per person in local currency, when the source has it (Google).
    # Scoring prefers this over price_level.
    price_per_person: Optional[float] = None
    price_reports: int = 0

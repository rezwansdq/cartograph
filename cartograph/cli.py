from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from cartograph.geo import geocode, write_geojson
from cartograph.scoring import ScoreConfig, score_restaurants

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "site" / "data" / "restaurants.geojson"
LONDON_ON = (42.9849, -81.2453)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _write(rows, out: Path, city: str, source: str, config: ScoreConfig) -> None:
    meta = {
        "city": city,
        "source": source,
        "demo": source == "demo",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": vars(config),
        "count": len(rows),
    }
    write_geojson(out, rows, meta)
    print("Wrote %d scored restaurants to %s" % (len(rows), out))
    for row in rows[:10]:
        print(
            "  %5.1f  %-40s %.1f stars, %d reviews, %s"
            % (row["score"], row["name"][:40], row["rating"], row["review_count"], "$" * row["price_level"])
        )


def cmd_restaurants(args: argparse.Namespace) -> None:
    from cartograph.sources import yelp

    config = ScoreConfig(args.prior_reviews, args.price_exponent, args.min_reviews)
    lat, lon = geocode(args.city)
    print("Fetching restaurants around %s (%.4f, %.4f)..." % (args.city, lat, lon))
    raw_dir = ROOT / "data" / "raw" / ("yelp-" + _slug(args.city))
    restaurants = yelp.fetch_restaurants(lat, lon, args.radius_km, args.step_km, raw_dir=raw_dir)
    print("Fetched %d unique restaurants" % len(restaurants))
    _write(score_restaurants(restaurants, config), args.out, args.city, "yelp", config)


def cmd_yelp_open(args: argparse.Namespace) -> None:
    from cartograph.sources import yelp_open

    if not args.file.exists():
        raise SystemExit("Dataset file not found: %s" % args.file)
    if args.list_cities:
        for (city, state), count in yelp_open.top_cities(args.file):
            print("  %6d  %s, %s" % (count, city, state))
        return
    if not args.city:
        raise SystemExit("Pass --city (and ideally --state), or --list-cities to see options")

    config = ScoreConfig(args.prior_reviews, args.price_exponent, args.min_reviews)
    restaurants = yelp_open.load_restaurants(args.file, args.city, args.state)
    label = "%s, %s" % (args.city, args.state) if args.state else args.city
    print("Loaded %d open restaurants in %s" % (len(restaurants), label))
    out = args.out or ROOT / "data" / ("yelp-open-%s.geojson" % _slug(label))
    _write(score_restaurants(restaurants, config), out, label, "yelp-open-dataset", config)


def cmd_demo(args: argparse.Namespace) -> None:
    from cartograph.demo import demo_restaurants

    config = ScoreConfig(args.prior_reviews, args.price_exponent, args.min_reviews)
    rows = score_restaurants(demo_restaurants(*LONDON_ON), config)
    _write(rows, args.out, "London, ON (demo data)", "demo", config)


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(prog="cartograph")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_scoring_args(p: argparse.ArgumentParser, default_out: Optional[Path] = DEFAULT_OUT) -> None:
        p.add_argument("--out", type=Path, default=default_out)
        p.add_argument("--prior-reviews", type=int, default=50, help="Bayesian prior strength (default 50)")
        p.add_argument("--price-exponent", type=float, default=0.5, help="Cost penalty, 0 ignores price (default 0.5)")
        p.add_argument("--min-reviews", type=int, default=5)

    p = sub.add_parser("restaurants", help="Fetch real restaurants for a city and score them")
    p.add_argument("--city", default="London, Ontario, Canada")
    p.add_argument("--radius-km", type=float, default=8.0)
    p.add_argument("--step-km", type=float, default=2.0)
    add_scoring_args(p)
    p.set_defaults(func=cmd_restaurants)

    p = sub.add_parser("yelp-open", help="Score restaurants from the downloaded Yelp Open Dataset")
    p.add_argument(
        "--file",
        type=Path,
        default=ROOT / "data" / "yelp-open" / "yelp_academic_dataset_business.json",
        help="Path to yelp_academic_dataset_business.json",
    )
    p.add_argument("--city")
    p.add_argument("--state")
    p.add_argument("--list-cities", action="store_true", help="Show the cities with the most restaurants")
    # Written under data/ (git-ignored) by default until the dataset licence is confirmed for publishing.
    add_scoring_args(p, default_out=None)
    p.set_defaults(func=cmd_yelp_open)

    p = sub.add_parser("demo", help="Write synthetic demo data so the map works without an API key")
    add_scoring_args(p)
    p.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    args.func(args)

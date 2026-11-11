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
DEFAULT_OUT = ROOT / "data" / "restaurants.geojson"
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


def _merge_metros(out_dir: Path, entries, config: ScoreConfig) -> None:
    """Add or replace metros in site/data/value/metros.json, keyed by slug."""
    import json

    path = out_dir / "metros.json"
    existing = json.loads(path.read_text())["metros"] if path.exists() else []
    by_slug = {m["slug"]: m for m in existing}
    for m in entries:
        by_slug[m["slug"]] = m
    metros = sorted(by_slug.values(), key=lambda m: (m.get("country") != "CA", -m["count"]))
    path.write_text(json.dumps({"config": vars(config), "metros": metros}, ensure_ascii=False, indent=1))


def _bounds(rows):
    lats = sorted(r["lat"] for r in rows)
    lons = sorted(r["lon"] for r in rows)
    q = lambda xs, t: xs[int(t * (len(xs) - 1))]
    return [[q(lons, 0.02), q(lats, 0.02)], [q(lons, 0.98), q(lats, 0.98)]]


def cmd_gmaps_value(args: argparse.Namespace) -> None:
    from cartograph.sources import gmaps

    raw_dir = args.raw_dir or ROOT / "data" / "gmaps" / args.slug / "raw"
    places = [p for p in gmaps.load_raw_dir(raw_dir) if gmaps.is_food_place(p.categories)]
    if args.bbox:
        s, w, n, e = [float(x) for x in args.bbox.split(",")]
        places = [p for p in places if s <= p.lat <= n and w <= p.lon <= e]
    with_reports = sum(p.price_reports > 0 for p in places)
    gmaps.fill_missing_prices(places)
    config = ScoreConfig(args.prior_reviews, args.price_exponent, args.min_reviews)
    rows = []
    for s_ in score_restaurants(places, config):
        rows.append({
            "name": s_["name"],
            "lat": round(s_["lat"], 5),
            "lon": round(s_["lon"], 5),
            "rating": s_["rating"],
            "review_count": s_["review_count"],
            "price_per_person": round(s_["price_per_person"], 1),
            "price_reports": s_["price_reports"],
            "price_level": gmaps.price_level_for(s_["price_per_person"]),
            "adjusted_rating": s_["adjusted_rating"],
            "raw_value": s_["raw_value"],
            "score": s_["score"],
            "categories": s_["categories"][:3],
            "address": s_["address"],
        })
    if not rows:
        raise SystemExit("No scored places in %s" % raw_dir)
    write_geojson(args.out_dir / ("%s.geojson" % args.slug), rows)
    _merge_metros(args.out_dir, [{
        "slug": args.slug, "name": args.name, "count": len(rows), "bounds": _bounds(rows),
        "source": "google", "country": "CA",
    }], config)
    print("%s: %d places scored, %d had reviewer price reports" % (args.name, len(rows), with_reports))
    for r in rows[:10]:
        print("  %5.1f  %-35s %.1f stars, %d reviews, ~$%.0f pp (%d reports)" % (
            r["score"], r["name"][:35], r["rating"], r["review_count"], r["price_per_person"], r["price_reports"]))


def cmd_yelp_value(args: argparse.Namespace) -> None:
    import json

    from cartograph.sources import yelp_open

    if not args.file.exists():
        raise SystemExit("Dataset file not found: %s" % args.file)
    config = ScoreConfig(args.prior_reviews, args.price_exponent, args.min_reviews)
    grouped = yelp_open.restaurants_by_metro(args.file)
    keep = ("name", "rating", "review_count", "price_level", "adjusted_rating", "raw_value", "score", "address")
    index = []
    for metro in yelp_open.METROS:
        scored = score_restaurants(grouped[metro["slug"]], config)
        rows = []
        for s in scored:
            row = {k: s[k] for k in keep}
            row["lat"], row["lon"] = round(s["lat"], 5), round(s["lon"], 5)
            row["categories"] = s["categories"][:3]
            rows.append(row)
        lats = sorted(r["lat"] for r in rows)
        lons = sorted(r["lon"] for r in rows)
        q = lambda xs, t: xs[int(t * (len(xs) - 1))]
        write_geojson(args.out_dir / ("%s.geojson" % metro["slug"]), rows)
        index.append({
            "slug": metro["slug"],
            "name": metro["name"],
            "country": "CA" if metro["slug"] == "edmonton" else "US",
            "count": len(rows),
            "bounds": [[q(lons, 0.02), q(lats, 0.02)], [q(lons, 0.98), q(lats, 0.98)]],
        })
        print("%-14s %5d scored" % (metro["name"], len(rows)))
    for m in index:
        m["source"] = "yelp"
    _merge_metros(args.out_dir, index, config)


def cmd_osm_food(args: argparse.Namespace) -> None:
    import json
    import time
    from collections import Counter

    from cartograph.cities import CITIES, by_slug
    from cartograph.sources import osm

    out_dir = args.out_dir
    index_path = out_dir / "cities.json"
    index = {c["slug"]: c for c in json.loads(index_path.read_text())} if index_path.exists() else {}
    targets = CITIES if args.city == "all" else [by_slug(args.city)]

    for i, city in enumerate(targets):
        if i:
            time.sleep(10)  # be polite to the public Overpass server
        rows = osm.mark_chains(osm.parse_places(osm.fetch_elements(city["wikidata"])))
        lats = sorted(r["lat"] for r in rows)
        lons = sorted(r["lon"] for r in rows)
        q = lambda xs, t: xs[int(t * (len(xs) - 1))]
        chains = sum(r["chain"] for r in rows)
        summary = {
            "slug": city["slug"],
            "name": city["name"],
            "region": city["region"],
            "count": len(rows),
            "chains": chains,
            "types": dict(Counter(r["type"] for r in rows)),
            "top_cuisines": Counter(c for r in rows for c in r["cuisines"]).most_common(12),
            "late_known": sum(r["late"] is not None for r in rows),
            "late": sum(bool(r["late"]) for r in rows),
            "bounds": [[q(lons, 0.02), q(lats, 0.02)], [q(lons, 0.98), q(lats, 0.98)]],
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        write_geojson(out_dir / ("%s.geojson" % city["slug"]), rows, {"attribution": "© OpenStreetMap contributors (ODbL)"})
        index[city["slug"]] = summary
        print("%-20s %5d places, %d chains" % (city["name"], len(rows), chains))

    ordered = [index[c["slug"]] for c in CITIES if c["slug"] in index]
    index_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=1))


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

    p = sub.add_parser("yelp-value", help="Score every Yelp Open Dataset metro and write the site's value map data")
    p.add_argument(
        "--file",
        type=Path,
        default=ROOT / "data" / "yelp-open" / "yelp_academic_dataset_business.json",
    )
    p.add_argument("--out-dir", type=Path, default=ROOT / "site" / "data" / "value")
    p.add_argument("--prior-reviews", type=int, default=50)
    p.add_argument("--price-exponent", type=float, default=0.5)
    p.add_argument("--min-reviews", type=int, default=5)
    p.set_defaults(func=cmd_yelp_value)

    p = sub.add_parser("gmaps-value", help="Score a city scraped from Google Maps and add it to the value map")
    p.add_argument("--slug", required=True, help="e.g. london")
    p.add_argument("--name", required=True, help="Display name, e.g. 'London, ON'")
    p.add_argument("--raw-dir", type=Path, help="Folder of raw-*.json dumps (default data/gmaps/<slug>/raw)")
    p.add_argument("--bbox", help="Keep only places inside 'south,west,north,east'")
    p.add_argument("--out-dir", type=Path, default=ROOT / "site" / "data" / "value")
    p.add_argument("--prior-reviews", type=int, default=50)
    p.add_argument("--price-exponent", type=float, default=0.5)
    p.add_argument("--min-reviews", type=int, default=5)
    p.set_defaults(func=cmd_gmaps_value)

    p = sub.add_parser("osm-food", help="Fetch restaurants, cafes and fast food for a city from OpenStreetMap")
    p.add_argument("--city", default="all", help="City slug from cartograph/cities.py, or 'all' (default)")
    p.add_argument("--out-dir", type=Path, default=ROOT / "site" / "data" / "food")
    p.set_defaults(func=cmd_osm_food)

    p = sub.add_parser("demo", help="Write synthetic demo data so the map works without an API key")
    add_scoring_args(p)
    p.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    args.func(args)

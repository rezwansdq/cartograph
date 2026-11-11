# Cartograph

Collect place data from the web and turn it into maps.

**Live site:** https://rezwansdq.github.io/cartograph/

## Maps

### Restaurant value

Which restaurants give you the most for your money? Each place gets a 0 to 100
value score from its star rating and its price level.

1. **Adjust the rating for review count** (Bayesian average). A 5.0 with three
   reviews gets pulled toward the city average; a 4.7 with 900 reviews barely moves.
   `adjusted = (n * rating + m * city_mean) / (n + m)`, with `m = 50` by default.
2. **Divide by cost.** `value = adjusted / price_level ** 0.5`. The exponent sets
   how much cost matters: `0` ignores price, `1` is a strict stars-per-dollar-sign ratio.
3. **Rank within the city.** A score of 90 means better value than 90% of places.

Both knobs are CLI flags (`--prior-reviews`, `--price-exponent`), so it's easy to try variations.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

Generate demo data (randomly generated, no API key needed):

```bash
cartograph demo
```

Fetch real restaurants. Needs a Yelp API key in `.env` (copy `.env.example`):

```bash
cartograph restaurants --city "London, Ontario, Canada" --radius-km 8
```

Both write `site/data/restaurants.geojson`. Preview the site locally:

```bash
python3 -m http.server -d site 8000
```

Then open http://localhost:8000.

## Data sources

| Source | Used for | Notes |
| --- | --- | --- |
| [Yelp Fusion API](https://docs.developer.yelp.com/) | Ratings, review counts, price | Official API. Scraping yelp.com directly is against Yelp's terms. |
| [OpenStreetMap Nominatim](https://nominatim.org/) | Geocoding city names | Free, rate limited to 1 request/second. |
| [OpenFreeMap](https://openfreemap.org/) | Basemap tiles | Free, no key. |

Raw API responses are cached under `data/raw/` (git-ignored). Check each source's
terms before publishing data derived from it.

## Layout

```
cartograph/          Python pipeline
  sources/           One module per data source
  scoring.py         Restaurant value score
  geo.py             Geocoding, grid tiling, GeoJSON export
  cli.py             `cartograph` command
site/                Static site (deployed to GitHub Pages)
  data/              Processed GeoJSON the maps load
  restaurants/       Restaurant value map
tests/
```

## Adding a map

1. Add a fetcher in `cartograph/sources/`.
2. Add a CLI subcommand that writes GeoJSON to `site/data/`.
3. Add a page under `site/<map-name>/` and a card in `site/index.html`.

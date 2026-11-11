# Cartograph

Collect place data from the web and turn it into maps.

**Live site:** https://map.rsadeqi.com

## Maps

### City food map

Every restaurant, cafe and fast food spot that OpenStreetMap has for London, Toronto,
Ottawa, Hamilton, Kitchener-Waterloo, Montréal, Vancouver and Calgary. Colour by type
or chain vs independent, filter by cuisine or late-night hours, and compare how
chain-heavy each city is. Cities live in `cartograph/cities.py`.

```bash
cartograph osm-food              # all cities
cartograph osm-food --city london
```

Data © OpenStreetMap contributors, ODbL.

### Restaurant value

Which restaurants give you the most for your money? Each place gets a 0 to 100
value score from its star rating and its price level. Covers the 11 metro areas in the
[Yelp Open Dataset](https://www.yelp.com/dataset) (Philadelphia, Tampa Bay, Nashville,
Indianapolis, St. Louis, New Orleans, Tucson, Edmonton, Reno, Boise, Santa Barbara).

1. **Adjust the rating for review count** (Bayesian average). A 5.0 with three
   reviews gets pulled toward the city average; a 4.7 with 900 reviews barely moves.
   `adjusted = (n * rating + m * city_mean) / (n + m)`, with `m = 50` by default.
2. **Subtract a quality floor, then divide by cost.**
   `value = max(adjusted - 3, 0) / price_level ** 0.5`. Stars at or below 3 count for
   nothing, so a cheap but mediocre place can't win on price alone. The exponent sets
   how much cost matters: `0` ignores price, `1` is a strict per-dollar-sign ratio.
3. **Rank within the city.** A score of 90 means better value than 90% of places.

Both knobs are CLI flags (`--prior-reviews`, `--price-exponent`), so it's easy to try variations.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

Build the value map data from the Yelp Open Dataset. Download it from
https://www.yelp.com/dataset, then put `yelp_academic_dataset_business.json` in
`data/yelp-open/` (git-ignored):

```bash
cartograph yelp-value                     # writes site/data/value/
cartograph yelp-open --list-cities        # explore one city at a time
cartograph yelp-open --city Philadelphia --state PA
```

Canadian cities come from Google Maps, scraped with
[gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper) (v1.18.2) plus
`scripts/gmaps-scraper-dump.patch`, which saves each place's raw data so we can read the
"price per person" answers in its reviews (Google no longer exposes a place-level price):

```bash
git -C ~/tools/google-maps-scraper apply ~/projects/cartograph/scripts/gmaps-scraper-dump.patch
go build -o ~/tools/gmaps-scraper ~/tools/google-maps-scraper
mkdir -p data/gmaps/london/raw && echo restaurants > data/gmaps/london/query.txt
GMAPS_DUMP_DIR=$PWD/data/gmaps/london/raw ~/tools/gmaps-scraper -input data/gmaps/london/query.txt \
  -results data/gmaps/london/results.json -json -grid-bbox "42.90,-81.40,43.06,-81.12" \
  -grid-cell 2.0 -zoom 15 -depth 2 -c 3 -exit-on-inactivity 4m
cartograph gmaps-value --slug london --name London --bbox "42.88,-81.42,43.08,-81.10"
```

Price per person is the median of reviewers' answers; places with none get the median for
their category in that city. Every $15 per person counts as one price level.

Other sources the scorer can use:

```bash
cartograph restaurants --city "London, Ontario, Canada"   # Yelp Fusion API, needs YELP_API_KEY in .env
cartograph demo                                           # random demo data
```

Preview the site locally:

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

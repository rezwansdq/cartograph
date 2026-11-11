"""Scrape and score a list of cities from Google Maps, one after another.

Usage: python scripts/scrape_cities.py [slug ...]   (default: all cities below)

Each city: run the patched google-maps-scraper over a 2 km grid, then
`cartograph gmaps-value`. Stops early if a city comes back nearly empty,
which usually means Google has started blocking us.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRAPER = Path.home() / "tools" / "gmaps-scraper"
CARTOGRAPH = ROOT / ".venv" / "bin" / "cartograph"

# slug: (display name, "south,west,north,east") — urban areas, not full municipal limits
CITIES = {
    "mississauga": ("Mississauga", "43.47,-79.81,43.74,-79.52"),
    "toronto": ("Toronto", "43.58,-79.64,43.86,-79.11"),
    "ottawa": ("Ottawa", "45.25,-75.95,45.50,-75.55"),
    "hamilton": ("Hamilton", "43.18,-80.05,43.30,-79.70"),
    "kitchener-waterloo": ("Kitchener-Waterloo", "43.36,-80.62,43.53,-80.38"),
    "oakville": ("Oakville", "43.37,-79.81,43.53,-79.62"),
    "burlington": ("Burlington", "43.29,-79.96,43.43,-79.71"),
    "brampton": ("Brampton", "43.60,-79.89,43.85,-79.63"),
    "markham": ("Markham", "43.80,-79.43,43.96,-79.17"),
    "vaughan": ("Vaughan", "43.75,-79.71,43.92,-79.42"),
    "windsor": ("Windsor", "42.23,-83.12,42.36,-82.89"),
    "montreal": ("Montréal", "45.41,-73.97,45.70,-73.47"),
    "quebec-city": ("Québec City", "46.73,-71.45,46.90,-71.15"),
    "vancouver": ("Vancouver", "49.20,-123.23,49.32,-123.02"),
    "victoria": ("Victoria", "48.40,-123.45,48.50,-123.30"),
    "calgary": ("Calgary", "50.84,-114.32,51.21,-113.86"),
    "winnipeg": ("Winnipeg", "49.71,-97.35,49.99,-96.96"),
    "halifax": ("Halifax", "44.58,-63.72,44.71,-63.54"),
}


def pad(bbox: str, d: float = 0.02) -> str:
    s, w, n, e = [float(x) for x in bbox.split(",")]
    return "%.3f,%.3f,%.3f,%.3f" % (s - d, w - d, n + d, e + d)


def scrape(slug: str, bbox: str) -> int:
    city_dir = ROOT / "data" / "gmaps" / slug
    raw = city_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (city_dir / "query.txt").write_text("restaurants\n")
    before = len(list(raw.glob("raw-*.json")))
    env = dict(os.environ, GMAPS_DUMP_DIR=str(raw))
    log_path = city_dir / ("run-%d.log" % int(time.time()))
    with open(log_path, "w") as log:
        proc = subprocess.Popen(
            [str(SCRAPER), "-input", str(city_dir / "query.txt"), "-results", str(city_dir / "results.json"),
             "-json", "-grid-bbox", bbox, "-grid-cell", "2.0", "-zoom", "15", "-depth", "2", "-c", "3",
             "-exit-on-inactivity", "4m"],
            env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        # The scraper sometimes logs "scrapemate exited" and then hangs on browser shutdown.
        deadline, done_at = time.time() + 4 * 3600, None
        while proc.poll() is None and time.time() < deadline:
            time.sleep(15)
            if done_at is None and "scrapemate exited" in log_path.read_text(errors="ignore")[-2000:]:
                done_at = time.time()
            if done_at and time.time() - done_at > 60:
                break
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    return len(list(raw.glob("raw-*.json"))) - before


def main() -> None:
    slugs = sys.argv[1:] or list(CITIES)
    for slug in slugs:
        name, bbox = CITIES[slug]
        start = time.time()
        new = scrape(slug, bbox)
        print("[%s] %s: %d new pages in %.0f min" % (time.strftime("%H:%M"), name, new, (time.time() - start) / 60), flush=True)
        result = subprocess.run(
            [str(CARTOGRAPH), "gmaps-value", "--slug", slug, "--name", name, "--bbox", pad(bbox)],
            capture_output=True, text=True,
        )
        print((result.stdout or result.stderr).strip().splitlines()[0] if (result.stdout or result.stderr) else "no output", flush=True)
        if new < 30:
            print("Stopping: %s returned almost nothing, Google may be blocking." % name, flush=True)
            break
        time.sleep(60)  # pause between cities


if __name__ == "__main__":
    main()

import json

from cartograph.sources.yelp_open import load_restaurants, parse_business, top_cities


def biz(id, city="Philadelphia", state="PA", cats="Restaurants, Pizza", is_open=1, price="2", stars=4.0):
    return {
        "business_id": id,
        "name": id,
        "address": "1 Main St",
        "city": city,
        "state": state,
        "latitude": 39.95,
        "longitude": -75.16,
        "stars": stars,
        "review_count": 100,
        "is_open": is_open,
        "attributes": {"RestaurantsPriceRange2": price} if price is not None else None,
        "categories": cats,
    }


def write_jsonl(tmp_path, rows):
    path = tmp_path / "business.json"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def test_parse_price_and_categories():
    r = parse_business(biz("a", cats="Restaurants, Food, Thai", price="3"))
    assert r.price_level == 3
    assert r.categories == ["Thai"]
    assert r.address == "1 Main St, Philadelphia, PA"


def test_bad_or_missing_price_is_none():
    for price in (None, "None", "", "7"):
        assert parse_business(biz("a", price=price)).price_level is None


def test_load_filters_city_state_open_and_category(tmp_path):
    path = write_jsonl(
        tmp_path,
        [
            biz("keep"),
            biz("keep-case", city=" philadelphia "),
            biz("closed", is_open=0),
            biz("not-restaurant", cats="Bars, Nightlife"),
            biz("other-city", city="Tampa", state="FL"),
            biz("other-state", state="NJ"),
        ],
    )
    ids = sorted(r.id for r in load_restaurants(path, "Philadelphia", "PA"))
    assert ids == ["keep", "keep-case"]


def test_top_cities(tmp_path):
    path = write_jsonl(tmp_path, [biz("a"), biz("b"), biz("c", city="Tampa", state="FL")])
    assert top_cities(path)[0] == (("Philadelphia", "PA"), 2)

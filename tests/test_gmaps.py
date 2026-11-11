from cartograph.models import Restaurant
from cartograph.scoring import ScoreConfig, cost_units, score_restaurants
from cartograph.sources.gmaps import fill_missing_prices, parse_place, price_level_for, price_midpoint


def raw_place(name="Place", rating=4.5, count=200, prices=("CA$20–30", "CA$20 to CA$30", "CA$10–20"), cats=("Pizza restaurant",)):
    place = [None] * 180
    place[4] = [None, None, None, None, None, None, None, rating, count]
    place[9] = [None, None, 42.98, -81.25]
    place[11] = name
    place[13] = list(cats)
    place[39] = "1 Main St, London, ON"
    place[78] = "pid-" + name
    place[175] = [[["review", [[[None, list(prices)]]]]]]
    return [None, None, None, None, None, None, place]


def r(id, rating, reviews, ppp):
    return Restaurant(id=id, name=id, lat=0, lon=0, rating=rating, review_count=reviews, price_level=None, price_per_person=ppp)


def test_price_midpoint_formats():
    assert price_midpoint("CA$20–30") == 25.0
    assert price_midpoint("CA$1–10") == 5.5
    assert price_midpoint("CA$100+") == 110.0
    assert price_midpoint("$20–30") == 25.0
    assert price_midpoint("CA$20 to CA$30") is None
    assert price_midpoint("Great prices!") is None


def test_parse_place_takes_median_of_review_prices():
    p = parse_place(raw_place())
    assert p.name == "Place" and p.rating == 4.5 and p.review_count == 200
    assert p.price_reports == 2 and p.price_per_person == 20.0
    assert p.lat == 42.98 and p.categories == ["Pizza restaurant"]


def test_parse_place_without_prices():
    p = parse_place(raw_place(prices=()))
    assert p.price_per_person is None and p.price_reports == 0


def test_fill_missing_prices_uses_category_then_city():
    rows = [
        Restaurant("a", "a", 0, 0, 4, 10, None, ["Pizza"], price_per_person=10),
        Restaurant("b", "b", 0, 0, 4, 10, None, ["Pizza"], price_per_person=12),
        Restaurant("c", "c", 0, 0, 4, 10, None, ["Pizza"], price_per_person=14),
        Restaurant("d", "d", 0, 0, 4, 10, None, ["Pizza"]),
        Restaurant("e", "e", 0, 0, 4, 10, None, ["Sushi"]),
    ]
    filled = {x.id: x.price_per_person for x in fill_missing_prices(rows)}
    assert filled["d"] == 12
    assert filled["e"] == 12  # city median of 10, 12, 14
    assert rows[3].price_reports == 0


def test_cost_units_from_dollars():
    cfg = ScoreConfig()
    assert cost_units(r("x", 4, 10, 10), cfg) == 1.0
    assert cost_units(r("x", 4, 10, 60), cfg) == 4.0


def test_cheaper_per_person_wins_at_equal_quality():
    rows = score_restaurants([r("cheap", 4.6, 500, 12), r("pricey", 4.6, 500, 55)])
    assert rows[0]["id"] == "cheap"


def test_price_buckets():
    assert [price_level_for(v) for v in (5, 15, 29, 30, 59, 60, None)] == [1, 2, 2, 3, 3, 4, None]


def test_food_filter():
    from cartograph.sources.gmaps import is_food_place

    assert is_food_place(["Italian restaurant"])
    assert is_food_place(["Coffee shop"])
    assert not is_food_place(["Golf course", "Country club"])
    assert not is_food_place([])

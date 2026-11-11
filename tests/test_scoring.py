from cartograph.models import Restaurant
from cartograph.scoring import ScoreConfig, bayesian_rating, percentile_ranks, score_restaurants
from cartograph.sources.yelp import parse_business


def r(id, rating, reviews, price):
    return Restaurant(id=id, name=id, lat=0, lon=0, rating=rating, review_count=reviews, price_level=price)


def test_bayesian_pulls_small_samples_toward_mean():
    assert bayesian_rating(5.0, 3, 4.0, 50) < bayesian_rating(4.7, 900, 4.0, 50)


def test_bayesian_with_no_prior_is_raw_rating():
    assert bayesian_rating(4.5, 10, 3.0, 0) == 4.5


def test_percentiles_span_0_to_100_and_share_ties():
    assert percentile_ranks([1, 2, 3]) == [0.0, 50.0, 100.0]
    ranks = percentile_ranks([1, 2, 2, 3])
    assert ranks[1] == ranks[2]
    assert percentile_ranks([7]) == [100.0]
    assert percentile_ranks([]) == []


def test_cheaper_wins_at_equal_quality():
    rows = score_restaurants([r("cheap", 4.5, 200, 1), r("pricey", 4.5, 200, 4)])
    assert rows[0]["id"] == "cheap"


def test_price_exponent_zero_ignores_cost():
    rows = score_restaurants(
        [r("cheap", 4.0, 200, 1), r("pricey", 4.8, 200, 4)], ScoreConfig(price_exponent=0)
    )
    assert rows[0]["id"] == "pricey"


def test_filters_missing_price_and_few_reviews():
    rows = score_restaurants([r("a", 4.5, 100, None), r("b", 4.5, 2, 2), r("c", 4.0, 100, 2)])
    assert [row["id"] for row in rows] == ["c"]


def test_parse_yelp_business():
    b = {
        "id": "x1",
        "name": "Place",
        "coordinates": {"latitude": 42.9, "longitude": -81.2},
        "rating": 4.5,
        "review_count": 120,
        "price": "$$",
        "categories": [{"alias": "thai", "title": "Thai"}],
        "location": {"display_address": ["1 Main St", "London, ON"]},
    }
    rest = parse_business(b)
    assert rest.price_level == 2
    assert rest.categories == ["Thai"]
    assert rest.address == "1 Main St, London, ON"
    assert parse_business({"id": "y", "coordinates": {}}) is None


def test_quality_floor_stops_cheap_mediocre_places_winning():
    rows = score_restaurants([r("cheap-meh", 3.0, 300, 1), r("good-mid", 4.5, 300, 2)])
    assert rows[0]["id"] == "good-mid"

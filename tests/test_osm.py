from cartograph.sources.osm import cuisines, mark_chains, open_late, parse_places


def el(id, name, amenity="restaurant", **tags):
    return {"type": "node", "id": id, "lat": 43.0, "lon": -81.2, "tags": dict(name=name, amenity=amenity, **tags)}


def test_open_late():
    assert open_late(None) is None
    assert open_late("Mo-Su 09:00-17:00") is False
    assert open_late("Mo-Fr 11:00-23:00") is True
    assert open_late("Fr,Sa 18:00-02:00") is True
    assert open_late("24/7") is True
    assert open_late("sunrise-sunset") is None


def test_cuisines_split_and_prettify():
    assert cuisines({"cuisine": "coffee_shop;bubble_tea"}) == ["Coffee shop", "Bubble tea"]
    assert cuisines({}) == []


def test_parse_skips_unnamed_and_uses_way_centers():
    elements = [
        el(1, "A"),
        {"type": "node", "id": 2, "lat": 1, "lon": 1, "tags": {"amenity": "cafe"}},
        {"type": "way", "id": 3, "center": {"lat": 43.1, "lon": -81.3}, "tags": {"name": "B", "amenity": "cafe"}},
    ]
    rows = parse_places(elements)
    assert [r["name"] for r in rows] == ["A", "B"]
    assert rows[1]["type"] == "Cafe" and rows[1]["id"] == "way/3"


def test_chains_from_brand_tag_or_repeated_name():
    rows = mark_chains(
        parse_places(
            [
                el(1, "Tim Hortons", "cafe", brand="Tim Hortons"),
                el(2, "Pizza Place"), el(3, "pizza place"), el(4, "Pizza Place"),
                el(5, "Solo Bistro"),
            ]
        )
    )
    chain = {r["id"]: r["chain"] for r in rows}
    assert chain == {"node/1": True, "node/2": True, "node/3": True, "node/4": True, "node/5": False}

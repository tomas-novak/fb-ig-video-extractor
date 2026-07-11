"""Testy vyhledávání (/hledej) a řazení míst podle vzdálenosti (poslaná poloha)."""
from conftest import make_place
from main import _fold, nearest_places, search_places


class TestFold:
    def test_removes_diacritics(self):
        assert _fold("Hřiště") == "hriste"

    def test_lowercases(self):
        assert _fold("TOBOGÁN") == "tobogan"

    def test_plain_ascii_unchanged(self):
        assert _fold("bazen") == "bazen"


class TestSearchPlaces:
    def test_finds_by_name_without_diacritics(self):
        places = [make_place(location_name="Dětské hřiště Napajedla")]
        assert len(search_places(places, "hriste")) == 1

    def test_finds_by_tags(self):
        places = [make_place(tags="tobogán,skluzavka")]
        assert len(search_places(places, "tobogan")) == 1

    def test_no_match(self):
        places = [make_place()]
        assert search_places(places, "lyžování") == []

    def test_empty_query(self):
        assert search_places([make_place()], "   ") == []

    def test_name_match_ranks_above_summary_match(self):
        in_summary = make_place(row=2, location_name="Aquapark",
                                summary="Vedle je krásné hřiště.", tags="")
        in_name = make_place(row=3, location_name="Hřiště Slaný",
                             summary="", tags="")
        hits = search_places([in_summary, in_name], "hriste")
        assert hits[0]["row"] == 3

    def test_merged_group_returned_once(self):
        a = make_place(row=2, group_id="g1", location_name="Koupaliště Slaný")
        b = make_place(row=3, group_id="g1", location_name="Aquapark Slaný")
        hits = search_places([a, b], "slany")
        assert len(hits) == 1

    def test_group_searches_all_name_variants(self):
        # reprezentant je první řádek, ale hledat se musí i v názvech ostatních
        a = make_place(row=2, group_id="g1", location_name="Plovárna")
        b = make_place(row=3, group_id="g1", location_name="Aquapark Slaný")
        assert len(search_places([a, b], "aquapark")) == 1

    def test_group_visited_is_aggregated(self):
        a = make_place(row=2, group_id="g1", visited=False)
        b = make_place(row=3, group_id="g1", visited=True)
        hits = search_places([a, b], "slany")
        assert hits[0]["visited"] is True

    def test_limit_five(self):
        places = [make_place(row=i, location_name=f"Hřiště {i}") for i in range(2, 12)]
        assert len(search_places(places, "hriste")) == 5


class TestNearestPlaces:
    USER = (50.0, 14.0)

    def test_sorted_by_distance(self):
        near = make_place(row=2, lat=50.01, lng=14.0)
        far = make_place(row=3, lat=50.5, lng=14.0)
        ranked = nearest_places([far, near], *self.USER)
        assert [p["row"] for _, p in ranked] == [2, 3]

    def test_visited_places_excluded(self):
        v = make_place(row=2, visited=True)
        ranked = nearest_places([v], *self.USER)
        assert ranked == []

    def test_visited_group_excluded_entirely(self):
        # návštěva jednoho řádku skupiny = celá skupina navštívená
        a = make_place(row=2, group_id="g1", visited=True)
        b = make_place(row=3, group_id="g1", visited=False)
        assert nearest_places([a, b], *self.USER) == []

    def test_group_counted_once_with_closest_coords(self):
        a = make_place(row=2, group_id="g1", lat=50.3, lng=14.0)
        b = make_place(row=3, group_id="g1", lat=50.01, lng=14.0)
        ranked = nearest_places([a, b], *self.USER)
        assert len(ranked) == 1
        assert ranked[0][1]["row"] == 3  # reprezentant = bližší záznam

    def test_distance_value(self):
        p = make_place(row=2, lat=51.0, lng=14.0)  # ~111 km na sever
        (d, _), = nearest_places([p], *self.USER)
        assert 110 <= d <= 112

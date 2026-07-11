"""Testy dedup logiky: předfiltr párů podle vzdálenosti + parsování verdiktu."""
from conftest import make_place
from dedup import MAX_DISTANCE_KM, find_candidate_pairs, parse_verdict


class TestFindCandidatePairs:
    def test_close_places_are_candidates(self):
        a = make_place(row=2, lat=50.230, lng=14.086)
        b = make_place(row=3, lat=50.232, lng=14.090)  # pár set metrů
        pairs = find_candidate_pairs([a, b])
        assert len(pairs) == 1
        assert pairs[0][2] < 1.0  # vzdálenost v km

    def test_distant_places_are_not_candidates(self):
        a = make_place(row=2, lat=50.0, lng=14.0)   # Praha
        b = make_place(row=3, lat=49.2, lng=16.6)   # Brno
        assert find_candidate_pairs([a, b]) == []

    def test_same_group_is_skipped(self):
        a = make_place(row=2, group_id="abc123")
        b = make_place(row=3, group_id="abc123")
        assert find_candidate_pairs([a, b]) == []

    def test_different_groups_are_compared(self):
        a = make_place(row=2, group_id="aaa")
        b = make_place(row=3, group_id="bbb")
        assert len(find_candidate_pairs([a, b])) == 1

    def test_empty_group_ids_are_compared(self):
        # dvě místa bez group_id se nesmí tvářit jako "stejná skupina"
        a = make_place(row=2, group_id="")
        b = make_place(row=3, group_id="")
        assert len(find_candidate_pairs([a, b])) == 1

    def test_boundary_distance(self):
        # ~1° zeměpisné šířky = ~111 km; MAX_DISTANCE_KM je výrazně menší
        delta_deg = (MAX_DISTANCE_KM + 1) / 111.0
        a = make_place(row=2, lat=50.0, lng=14.0)
        b = make_place(row=3, lat=50.0 + delta_deg, lng=14.0)
        assert find_candidate_pairs([a, b]) == []


class TestParseVerdict:
    def test_same_true(self):
        v = parse_verdict('{"same": true, "reason": "Stejné koupaliště."}')
        assert v == {"same": True, "reason": "Stejné koupaliště."}

    def test_same_false(self):
        v = parse_verdict('{"same": false, "reason": "Různá místa."}')
        assert v["same"] is False

    def test_fenced_json(self):
        v = parse_verdict('```json\n{"same": true, "reason": "ok"}\n```')
        assert v["same"] is True

    def test_unparseable_fails_safe(self):
        # neparsovatelná odpověď nesmí navrhnout sloučení
        v = parse_verdict("Promiň, nedokážu rozhodnout.")
        assert v["same"] is False
        assert "neparsovatelná" in v["reason"]

    def test_missing_keys(self):
        v = parse_verdict("{}")
        assert v == {"same": False, "reason": ""}

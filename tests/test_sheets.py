"""Testy čistých funkcí ze sheets.py: normalizace URL a parsování řádků."""
from models import VideoMetadata
from sheets import NUM_COLS, _parse_row, normalize_url


class TestNormalizeUrl:
    def test_strips_query_string(self):
        assert normalize_url("https://fb.com/reel/1?fbclid=xyz") == "https://fb.com/reel/1"

    def test_strips_fragment(self):
        assert normalize_url("https://fb.com/reel/1#detail") == "https://fb.com/reel/1"

    def test_strips_trailing_slash(self):
        assert normalize_url("https://fb.com/reel/1/") == "https://fb.com/reel/1"

    def test_strips_whitespace(self):
        assert normalize_url("  https://fb.com/reel/1 ") == "https://fb.com/reel/1"

    def test_same_video_different_share_params_match(self):
        a = normalize_url("https://www.instagram.com/reel/ABC/?igsh=token1")
        b = normalize_url("https://www.instagram.com/reel/ABC/")
        assert a == b


def _row(overrides: dict | None = None) -> list:
    row = [""] * NUM_COLS
    row[0] = "2026-07-01 12:00"
    row[1] = "https://fb.com/reel/1"
    row[4] = "Koupaliště Slaný"
    row[5] = "50.23"
    row[6] = "14.09"
    row[7] = "koupání"
    for idx, value in (overrides or {}).items():
        row[idx] = value
    return row


class TestParseRow:
    def test_valid_row(self):
        p = _parse_row(_row(), 2)
        assert p["row"] == 2
        assert p["location_name"] == "Koupaliště Slaný"
        assert p["lat"] == 50.23
        assert p["category"] == "koupání"

    def test_header_row_is_skipped(self):
        header = ["Datum", "URL", "Autor", "Titulek", "Místo", "Lat", "Lng"] \
            + [""] * (NUM_COLS - 7)
        assert _parse_row(header, 1) is None

    def test_zero_coords_skipped(self):
        # 0,0 = Gemini místo neurčil – nemá co dělat na mapě
        assert _parse_row(_row({5: "0", 6: "0"}), 2) is None

    def test_comma_decimal_separator(self):
        p = _parse_row(_row({5: "50,23", 6: "14,09"}), 2)
        assert p["lat"] == 50.23

    def test_short_row_padded(self):
        # starší řádky nemají všechny sloupce
        p = _parse_row(_row()[:8], 2)
        assert p is not None
        assert p["group_id"] == ""
        assert p["visited"] is False

    def test_visited_variants(self):
        for value in ("ano", "TRUE", "1", "x"):
            assert _parse_row(_row({14: value}), 2)["visited"] is True
        assert _parse_row(_row({14: "ne"}), 2)["visited"] is False

    def test_missing_category_defaults(self):
        assert _parse_row(_row({7: ""}), 2)["category"] == "jiné"


class TestToSheetsRow:
    def test_row_matches_column_layout(self):
        m = VideoMetadata(url="https://fb.com/reel/1", location_name="Slaný",
                          lat=50.23, lng=14.09, category="koupání", source="facebook",
                          group_id="g1", video_id="123", place_id="ChIJx",
                          maps_url="https://maps...", geo_source="places")
        row = m.to_sheets_row()
        assert len(row) == NUM_COLS
        assert row[1] == "https://fb.com/reel/1"
        assert row[4] == "Slaný"
        assert row[12] == "g1"      # M: group_id
        assert row[14] == ""        # O: navštíveno – vyplňuje mapa
        assert row[15] == "ChIJx"   # P: place_id

    def test_roundtrip_through_parse_row(self):
        """to_sheets_row() -> _parse_row() musí vrátit konzistentní data."""
        m = VideoMetadata(url="https://fb.com/reel/1", location_name="Slaný",
                          lat=50.23, lng=14.09, category="koupání",
                          source="facebook", group_id="g1")
        p = _parse_row([str(v) for v in m.to_sheets_row()], 5)
        assert p["location_name"] == "Slaný"
        assert p["lat"] == 50.23
        assert p["group_id"] == "g1"
        assert p["visited"] is False

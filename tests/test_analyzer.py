"""Tests for parsing the Gemini response – without calling the API."""
import json

import pytest

from analyzer import _safe_float, parse_metadata, strip_fences

GEMINI_JSON = json.dumps({
    "transcript": "Ahoj, dneska jsme na koupališti ve Slaném.",
    "location_name": "Koupaliště Slaný",
    "city": "Slaný",
    "lat": 50.2305,
    "lng": 14.0869,
    "category": "koupání",
    "tags": "outdoor,s dětmi,bazén",
    "summary": "Moderní koupaliště s bazény pro děti i dospělé.",
}, ensure_ascii=False)


class TestStripFences:
    def test_plain_json_untouched(self):
        assert strip_fences('{"a": 1}') == '{"a": 1}'

    def test_json_fence(self):
        assert strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_plain_fence(self):
        assert strip_fences('```\n{"a": 1}\n```') == '{"a": 1}'

    def test_surrounding_whitespace(self):
        assert strip_fences('  {"a": 1}\n') == '{"a": 1}'


class TestParseMetadata:
    def test_full_response(self):
        m = parse_metadata(GEMINI_JSON, "https://www.facebook.com/reel/123",
                           author="Cestovatel", title="Výlet")
        assert m.location_name == "Koupaliště Slaný"
        assert m.city == "Slaný"
        assert m.lat == pytest.approx(50.2305)
        assert m.lng == pytest.approx(14.0869)
        assert m.category == "koupání"
        assert m.transcript.startswith("Ahoj")
        assert m.author == "Cestovatel"
        assert m.url == "https://www.facebook.com/reel/123"

    def test_source_from_url(self):
        assert parse_metadata("{}", "https://www.instagram.com/reel/x").source == "instagram"
        assert parse_metadata("{}", "https://www.facebook.com/reel/x").source == "facebook"
        assert parse_metadata("{}", "https://www.tiktok.com/@u/video/1").source == "tiktok"
        assert parse_metadata("{}", "https://www.youtube.com/shorts/x").source == "youtube"

    def test_fenced_response(self):
        m = parse_metadata(f"```json\n{GEMINI_JSON}\n```", "https://www.facebook.com/reel/1")
        assert m.location_name == "Koupaliště Slaný"

    def test_missing_fields_get_defaults(self):
        m = parse_metadata("{}", "https://www.facebook.com/reel/1")
        assert m.location_name == ""
        assert m.lat == 0.0
        assert m.lng == 0.0
        assert m.category == "jiné"

    def test_null_city_becomes_empty_string(self):
        m = parse_metadata('{"city": null}', "https://www.facebook.com/reel/1")
        assert m.city == ""

    def test_lat_lng_as_strings_with_comma(self):
        m = parse_metadata('{"lat": "50,23", "lng": "14,09"}',
                           "https://www.facebook.com/reel/1")
        assert m.lat == pytest.approx(50.23)
        assert m.lng == pytest.approx(14.09)

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_metadata("tohle není json", "https://www.facebook.com/reel/1")


class TestSafeFloat:
    def test_float(self):
        assert _safe_float(50.5) == 50.5

    def test_string_with_comma(self):
        assert _safe_float("50,5") == 50.5

    def test_none_is_zero(self):
        assert _safe_float(None) == 0.0

    def test_garbage_is_zero(self):
        assert _safe_float("neznámé") == 0.0

    def test_empty_string_is_zero(self):
        assert _safe_float("") == 0.0

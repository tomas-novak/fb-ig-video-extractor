"""Tests for exporting places to GeoJSON/GPX/KML."""
import json
import xml.etree.ElementTree as ET

import pytest
from fastapi import HTTPException

from conftest import make_place
from main import _build_export, _export_places


class TestExportPlaces:
    def test_solo_places_kept_separate(self):
        items = _export_places([make_place(row=2), make_place(row=3)])
        assert len(items) == 2

    def test_group_collapsed_to_one_with_all_urls(self):
        a = make_place(row=2, group_id="g1", url="https://fb.com/a")
        b = make_place(row=3, group_id="g1", url="https://fb.com/b")
        items = _export_places([a, b])
        assert len(items) == 1
        assert items[0]["urls"] == ["https://fb.com/a", "https://fb.com/b"]

    def test_group_visited_aggregated(self):
        a = make_place(row=2, group_id="g1", visited=False)
        b = make_place(row=3, group_id="g1", visited=True)
        assert _export_places([a, b])[0]["visited"] is True

    def test_empty_url_not_exported(self):
        items = _export_places([make_place(url="")])
        assert items[0]["urls"] == []


class TestBuildExport:
    def test_geojson(self):
        content, media_type, ext = _build_export([make_place()], "geojson")
        assert media_type == "application/geo+json"
        assert ext == "geojson"
        data = json.loads(content)
        assert data["type"] == "FeatureCollection"
        feature = data["features"][0]
        # GeoJSON uses the order [lng, lat]
        assert feature["geometry"]["coordinates"] == [14.09, 50.23]
        assert feature["properties"]["name"] == "Koupaliště Slaný"

    def test_gpx_is_valid_xml(self):
        content, media_type, ext = _build_export([make_place()], "gpx")
        assert media_type == "application/gpx+xml"
        root = ET.fromstring(content)
        wpt = root.find("{http://www.topografix.com/GPX/1/1}wpt")
        assert wpt.get("lat") == "50.23"
        assert wpt.get("lon") == "14.09"

    def test_kml_is_valid_xml(self):
        content, media_type, ext = _build_export([make_place()], "kml")
        assert "google-earth" in media_type
        root = ET.fromstring(content)
        name = root.find(".//{http://www.opengis.net/kml/2.2}Placemark/"
                         "{http://www.opengis.net/kml/2.2}name")
        assert name.text == "Koupaliště Slaný"

    def test_xml_special_chars_escaped(self):
        place = make_place(location_name="Bistro <U Pepy> & spol.")
        for fmt in ("gpx", "kml"):
            content, _, _ = _build_export([place], fmt)
            ET.fromstring(content)  # unescaped < & > would break the parser

    def test_unknown_format_raises_400(self):
        with pytest.raises(HTTPException) as e:
            _build_export([make_place()], "csv")
        assert e.value.status_code == 400

    def test_empty_places(self):
        content, _, _ = _build_export([], "geojson")
        assert json.loads(content)["features"] == []

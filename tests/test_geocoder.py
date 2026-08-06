"""Tests for the haversine distance and building Google Maps links."""
import pytest

from geocoder import distance_km, maps_link


class TestDistanceKm:
    def test_zero_distance(self):
        assert distance_km(50.0, 14.0, 50.0, 14.0) == 0.0

    def test_prague_brno(self):
        # Prague–Brno as the crow flies ~185 km
        d = distance_km(50.0755, 14.4378, 49.1951, 16.6068)
        assert d == pytest.approx(185, abs=5)

    def test_symmetric(self):
        assert distance_km(50.0, 14.0, 51.0, 15.0) == pytest.approx(
            distance_km(51.0, 15.0, 50.0, 14.0))

    def test_one_latitude_degree(self):
        # 1° of latitude ≈ 111 km anywhere on Earth
        assert distance_km(50.0, 14.0, 51.0, 14.0) == pytest.approx(111, abs=1)


class TestMapsLink:
    def test_place_id_with_coords(self):
        url = maps_link(place_id="ChIJabc", lat=50.23, lng=14.09)
        assert url == ("https://www.google.com/maps/search/?api=1"
                       "&query=50.23%2C14.09&query_place_id=ChIJabc")

    def test_place_id_with_name_only(self):
        url = maps_link(place_id="ChIJabc", name="Koupaliště Slaný")
        assert "query_place_id=ChIJabc" in url
        assert "api=1" in url
        assert " " not in url

    def test_place_id_without_query_falls_back_to_empty(self):
        # query_place_id bez query Google nepodporuje
        assert maps_link(place_id="ChIJabc") == ""

    def test_no_legacy_place_format(self):
        # the old ?q=place_id: format cannot be opened by the mobile app
        url = maps_link(place_id="ChIJabc", lat=50.0, lng=14.0)
        assert "/maps/place/?q=place_id:" not in url

    def test_name_fallback_is_url_encoded(self):
        url = maps_link(name="Koupaliště Slaný")
        assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
        assert " " not in url

    def test_empty(self):
        assert maps_link() == ""

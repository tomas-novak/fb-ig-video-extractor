"""Testy haversine vzdálenosti a stavby odkazů na Google Maps."""
import pytest

from geocoder import distance_km, maps_link


class TestDistanceKm:
    def test_zero_distance(self):
        assert distance_km(50.0, 14.0, 50.0, 14.0) == 0.0

    def test_prague_brno(self):
        # Praha–Brno vzdušnou čarou ~185 km
        d = distance_km(50.0755, 14.4378, 49.1951, 16.6068)
        assert d == pytest.approx(185, abs=5)

    def test_symmetric(self):
        assert distance_km(50.0, 14.0, 51.0, 15.0) == pytest.approx(
            distance_km(51.0, 15.0, 50.0, 14.0))

    def test_one_latitude_degree(self):
        # 1° šířky ≈ 111 km kdekoliv na Zemi
        assert distance_km(50.0, 14.0, 51.0, 14.0) == pytest.approx(111, abs=1)


class TestMapsLink:
    def test_place_id_wins(self):
        url = maps_link(place_id="ChIJabc", name="Koupaliště")
        assert url == "https://www.google.com/maps/place/?q=place_id:ChIJabc"

    def test_name_fallback_is_url_encoded(self):
        url = maps_link(name="Koupaliště Slaný")
        assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
        assert " " not in url

    def test_empty(self):
        assert maps_link() == ""

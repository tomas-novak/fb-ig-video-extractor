"""Tests for the map-popup thumbnail cache.

The module's whole contract (see its docstring) is that a thumbnail failure must
never break saving a place - main.py's process_video() has no try/except around
its save_thumbnail() call specifically because of that promise."""
import importlib

import pytest


@pytest.fixture
def thumbnails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("THUMB_DIR", "data/thumbnails")
    import thumbnails
    importlib.reload(thumbnails)
    return thumbnails


class TestSaveThumbnail:
    def test_copies_the_source_file(self, thumbnails, tmp_path):
        source = tmp_path / "source.jpg"
        source.write_bytes(b"fake jpeg bytes")
        thumbnails.save_thumbnail("https://example.com/place", source_path=str(source))
        assert open(thumbnails.thumbnail_path("https://example.com/place"), "rb").read() \
            == b"fake jpeg bytes"

    def test_never_raises_even_with_a_non_string_place_url(self, thumbnails, tmp_path):
        # Regression test: process_video() used to pass the numeric Sheets row
        # instead of metadata.url here. thumb_key()'s .encode() call raised
        # AttributeError on that int, which _save_from_file()'s narrower
        # `except OSError` didn't catch - taking process_video() down even
        # though the place had already been saved. Any place_url that isn't a
        # plain string must fail the same safe, silent way.
        source = tmp_path / "source.jpg"
        source.write_bytes(b"fake jpeg bytes")
        thumbnails.save_thumbnail(12345, source_path=str(source))  # no raise = pass

    def test_missing_source_file_does_not_raise(self, thumbnails):
        thumbnails.save_thumbnail("https://example.com/place",
                                  source_path="/no/such/file.jpg")

    def test_no_source_provided_does_not_raise(self, thumbnails):
        thumbnails.save_thumbnail("https://example.com/place")


class TestThumbKey:
    def test_same_url_gives_same_key(self, thumbnails):
        assert thumbnails.thumb_key("https://example.com/a") == \
            thumbnails.thumb_key("https://example.com/a")

    def test_different_urls_give_different_keys(self, thumbnails):
        assert thumbnails.thumb_key("https://example.com/a") != \
            thumbnails.thumb_key("https://example.com/b")

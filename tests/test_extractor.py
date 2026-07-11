"""Testy rozpoznání zdroje z URL."""
from extractor import extract_source


class TestExtractSource:
    def test_facebook(self):
        assert extract_source("https://www.facebook.com/reel/123") == "facebook"

    def test_fb_watch_share_link(self):
        assert extract_source("https://fb.watch/abc123/") == "facebook"

    def test_instagram_reel(self):
        assert extract_source("https://www.instagram.com/reel/ABC/") == "instagram"

    def test_instagram_post(self):
        assert extract_source("https://www.instagram.com/p/ABC/") == "instagram"

    def test_unknown(self):
        assert extract_source("https://www.youtube.com/shorts/xyz") == "unknown"

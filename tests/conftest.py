"""Shared test setup.

The tests run without real API keys – but main.py reads TELEGRAM_BOT_TOKEN
at import time, so we set it before anything is imported.
"""
import os
import sys

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN_NOT_REAL")

# Isolation from a local .env (main.py calls load_dotenv(), which does not
# overwrite existing variables): these variables have fail-closed validation at
# import time in main.py, and a developer's config could otherwise break the suite.
for _var in ("TELEGRAM_ALLOWED_USERS", "MAP_TOKEN", "MAP_VIEW_TOKEN",
             "CATEGORIES"):
    os.environ[_var] = ""
# The test fixtures and assertions are written in Czech – pin the language to cs
# regardless of the default value (en) and of the developer's .env.
os.environ["BOT_LANGUAGE"] = "cs"
# extractor.py reads the video length limit at import time – an invalid value
# in a developer's .env would break the import; the tests assume the default 10.
os.environ["MAX_VIDEO_MINUTES"] = "10"

# Import project modules from the repo root (tests run from the tests/ subfolder)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_place(**overrides) -> dict:
    """Factory for a place in the shape returned by sheets.read_rows()."""
    place = {
        "row": 2,
        "date": "2026-07-01 12:00",
        "url": "https://www.facebook.com/reel/123",
        "author": "autor",
        "title": "titulek",
        "location_name": "Koupaliště Slaný",
        "lat": 50.23,
        "lng": 14.09,
        "category": "koupání",
        "tags": "outdoor,s dětmi",
        "summary": "Moderní koupaliště s bazény.",
        "source": "facebook",
        "group_id": "",
        "video_id": "123",
        "visited": False,
        "place_id": "",
        "maps_url": "",
        "geo_source": "gemini",
    }
    place.update(overrides)
    return place

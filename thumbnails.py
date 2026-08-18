"""Local cache of small preview images shown in the map popup.

Best-effort, same philosophy as geocoder.py: a missing/failed thumbnail must
never break saving a place. Tries the video/photo's own source first (free,
already fetched as part of processing it); Google's Places Photo is only a
fallback for places with no source thumbnail of their own, since it has its
own separate free quota (1000 calls/month) that repeated per-view calls would
burn through fast - hence writing the result to disk once and reusing it.

Cache key is a hash of the place's own row URL (column B), NOT the sheet row
number: sheets.py's delete_place_rows() physically removes rows, shifting
every row below it up by one, and the same can happen from editing the sheet
by hand outside the app entirely - either way a row-number key would silently
end up pointing at the wrong place's photo. The URL is already the row's
natural stable identity (same value find_duplicate() dedupes on).

THUMB_DIR is a mounted Docker volume (see docker-compose.yml) so cached
thumbnails survive container rebuilds; served back via GET /thumb/<key>.jpg
in main.py.
"""
import hashlib
import os
import shutil

import httpx

THUMB_DIR = os.getenv("THUMB_DIR", "/app/data/thumbnails")


def thumb_key(place_url: str) -> str:
    return hashlib.md5(place_url.encode()).hexdigest()


def thumbnail_path(place_url: str) -> str:
    return os.path.join(THUMB_DIR, f"{thumb_key(place_url)}.jpg")


def delete_thumbnail(place_url: str) -> None:
    """Best-effort cleanup when a place is deleted."""
    try:
        os.remove(thumbnail_path(place_url))
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"[thumbnails] delete failed for {place_url}: {e}")


def _save_from_file(place_url: str, source_path: str) -> bool:
    try:
        os.makedirs(THUMB_DIR, exist_ok=True)
        shutil.copyfile(source_path, thumbnail_path(place_url))
        return True
    except OSError as e:
        print(f"[thumbnails] copy failed for {place_url}: {e}")
        return False


def _save_from_url(place_url: str, source_thumb_url: str) -> bool:
    try:
        os.makedirs(THUMB_DIR, exist_ok=True)
        with httpx.stream("GET", source_thumb_url, timeout=20, follow_redirects=True) as r:
            r.raise_for_status()
            with open(thumbnail_path(place_url), "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"[thumbnails] download failed for {place_url}: {e}")
        return False


def _save_from_place_photo(place_url: str, photo_name: str) -> bool:
    from geocoder import fetch_place_photo  # local import: avoids a hard dependency for callers that never need it
    data = fetch_place_photo(photo_name)
    if not data:
        return False
    try:
        os.makedirs(THUMB_DIR, exist_ok=True)
        with open(thumbnail_path(place_url), "wb") as f:
            f.write(data)
        return True
    except OSError as e:
        print(f"[thumbnails] write failed for {place_url}: {e}")
        return False


def save_thumbnail(place_url: str, *, source_path: str | None = None,
                    thumb_url: str | None = None, photo_name: str = "") -> None:
    """Try, in order: a locally-available source file, a source thumbnail URL
    (yt-dlp's own poster frame), then Google Places Photo as a last resort.
    Silently does nothing if all of them fail or none were provided."""
    if source_path and _save_from_file(place_url, source_path):
        return
    if thumb_url and _save_from_url(place_url, thumb_url):
        return
    if photo_name:
        _save_from_place_photo(place_url, photo_name)

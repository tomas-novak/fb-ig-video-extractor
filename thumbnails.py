"""Local cache of small preview images shown in the map popup.

Best-effort, same philosophy as geocoder.py: a missing/failed thumbnail must
never break saving a place. Tries the video/photo's own source first (free,
already fetched as part of processing it); Google's Places Photo is only a
fallback for places with no source thumbnail of their own, since it has its
own separate free quota (1000 calls/month) that repeated per-view calls would
burn through fast - hence writing the result to disk once and reusing it.

THUMB_DIR is a mounted Docker volume (see docker-compose.yml) so cached
thumbnails survive container rebuilds; served back via GET /thumb/<row>.jpg
in main.py.
"""
import os
import shutil

import httpx

THUMB_DIR = os.getenv("THUMB_DIR", "/app/data/thumbnails")


def thumbnail_path(row: int) -> str:
    return os.path.join(THUMB_DIR, f"{row}.jpg")


def _save_from_file(row: int, source_path: str) -> bool:
    try:
        os.makedirs(THUMB_DIR, exist_ok=True)
        shutil.copyfile(source_path, thumbnail_path(row))
        return True
    except OSError as e:
        print(f"[thumbnails] copy failed for row {row}: {e}")
        return False


def _save_from_url(row: int, url: str) -> bool:
    try:
        os.makedirs(THUMB_DIR, exist_ok=True)
        with httpx.stream("GET", url, timeout=20, follow_redirects=True) as r:
            r.raise_for_status()
            with open(thumbnail_path(row), "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"[thumbnails] download failed for row {row}: {e}")
        return False


def _save_from_place_photo(row: int, photo_name: str) -> bool:
    from geocoder import fetch_place_photo  # local import: avoids a hard dependency for callers that never need it
    data = fetch_place_photo(photo_name)
    if not data:
        return False
    try:
        os.makedirs(THUMB_DIR, exist_ok=True)
        with open(thumbnail_path(row), "wb") as f:
            f.write(data)
        return True
    except OSError as e:
        print(f"[thumbnails] write failed for row {row}: {e}")
        return False


def save_thumbnail(row: int, *, source_path: str | None = None,
                    thumb_url: str | None = None, photo_name: str = "") -> None:
    """Try, in order: a locally-available source file, a source thumbnail URL
    (yt-dlp's own poster frame), then Google Places Photo as a last resort.
    Silently does nothing if all of them fail or none were provided."""
    if source_path and _save_from_file(row, source_path):
        return
    if thumb_url and _save_from_url(row, thumb_url):
        return
    if photo_name:
        _save_from_place_photo(row, photo_name)

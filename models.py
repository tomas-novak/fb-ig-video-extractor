from dataclasses import dataclass, field
from datetime import datetime

from i18n import FALLBACK_CATEGORY


@dataclass
class VideoMetadata:
    url: str
    author: str = ""
    title: str = ""
    location_name: str = ""
    lat: float = 0.0
    lng: float = 0.0
    category: str = FALLBACK_CATEGORY
    tags: str = ""
    summary: str = ""
    transcript: str = ""
    source: str = ""
    group_id: str = ""
    video_id: str = ""
    place_id: str = ""
    maps_url: str = ""
    geo_source: str = ""   # "places" = exact from Google, "gemini" = AI estimate
    media_type: str = "video"  # "video" or "photo" – which prompt/mime analyze() used
    city: str = ""         # town – only for the geocoding query, not stored in the sheet
    created_at: datetime = field(default_factory=datetime.now)

    def to_sheets_row(self) -> list:
        return [
            self.created_at.strftime("%Y-%m-%d %H:%M"),
            self.url,
            self.author,
            self.title,
            self.location_name,
            self.lat,
            self.lng,
            self.category,
            self.tags,
            self.summary,
            self.transcript,
            self.source,
            self.group_id,
            self.video_id,
            "",  # O: visited (filled in by the button on the map)
            self.place_id,
            self.maps_url,
            self.geo_source,
            self.media_type,
        ]

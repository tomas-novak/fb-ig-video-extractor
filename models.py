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
    geo_source: str = ""   # "places" = přesné z Google, "gemini" = odhad AI
    city: str = ""         # obec – jen pro geokódovací dotaz, do tabulky se neukládá
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
            "",  # O: navštíveno (vyplňuje se tlačítkem na mapě)
            self.place_id,
            self.maps_url,
            self.geo_source,
        ]

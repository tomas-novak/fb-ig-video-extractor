from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class VideoMetadata:
    url: str
    author: str = ""
    title: str = ""
    location_name: str = ""
    lat: float = 0.0
    lng: float = 0.0
    category: str = "jiné"
    tags: str = ""
    summary: str = ""
    transcript: str = ""
    source: str = ""
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
        ]

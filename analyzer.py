import json
import os
import google.generativeai as genai
from models import VideoMetadata


_model = None


def _get_model():
    """Lazy init – Gemini se konfiguruje až při prvním použití, ne při importu."""
    global _model
    if _model is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Chybí proměnná prostředí GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-2.5-flash")
    return _model

SYSTEM_PROMPT = """Jsi AI asistent, který analyzuje cestovní videa. Dostaneš přepis mluveného slova z videa a URL.

Vrať POUZE validní JSON (bez markdown, bez dalšího textu) v tomto přesném formátu:
{
  "transcript": "plný přepis mluveného slova",
  "location_name": "název konkrétního místa (město, název objektu...)",
  "lat": 50.1234,
  "lng": 14.5678,
  "category": "koupání",
  "tags": "outdoor,s dětmi,bazén",
  "summary": "2-3 věty popisující místo a proč je zajímavé."
}

Pravidla:
- category: jedna z: koupání, turistika, jídlo, kultura, příroda, sport, zábava, jiné
- lat/lng: odhadni souřadnice podle názvu místa (česká republika nebo okolí)
- tags: max 4 tagy oddělené čárkou, bez mezer kolem čárek
- Pokud místo není jasné z přepisu, dedukuj z kontextu"""


def analyze(audio_path: str, url: str, yt_info: dict) -> VideoMetadata:
    """Send audio to Gemini, get transcript + metadata in one call."""
    model = _get_model()
    author = yt_info.get("uploader") or yt_info.get("channel") or ""
    title = yt_info.get("title") or yt_info.get("description", "")[:100] or ""

    audio_file = genai.upload_file(audio_path, mime_type="audio/mp3")

    prompt = f"""URL videa: {url}
Autor: {author}
Titulek/popis: {title}

Přepiš prosím mluvený projev z tohoto audia a extrahuj metadata o místě."""

    response = model.generate_content(
        [audio_file, SYSTEM_PROMPT + "\n\n" + prompt],
        generation_config=genai.GenerationConfig(
            temperature=0,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    # JSON mód garantuje čistý JSON, ale pro jistotu odstraníme případné fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)

    source = "instagram" if "instagram.com" in url else "facebook"

    return VideoMetadata(
        url=url,
        author=author,
        title=title,
        location_name=data.get("location_name", ""),
        lat=float(data.get("lat", 0)),
        lng=float(data.get("lng", 0)),
        category=data.get("category", "jiné"),
        tags=data.get("tags", ""),
        summary=data.get("summary", ""),
        transcript=data.get("transcript", ""),
        source=source,
    )

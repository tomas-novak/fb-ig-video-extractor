import json
import os
import time
import google.generativeai as genai
from extractor import extract_source
from models import VideoMetadata


_model = None


def _safe_float(v) -> float:
    """Bezpečný převod na float – Gemini může vrátit null, prázdno nebo text."""
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


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

_VIDEO_MIME = {
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".mkv": "video/x-matroska", ".m4v": "video/mp4", ".3gp": "video/3gpp",
}

SYSTEM_PROMPT = """Jsi AI asistent, který analyzuje cestovní videa. Dostaneš samotné video, jeho popisek (caption) a URL.

Vrať POUZE validní JSON (bez markdown, bez dalšího textu) v tomto přesném formátu:
{
  "transcript": "plný přepis mluveného slova",
  "location_name": "název konkrétního místa (název objektu/atrakce)",
  "city": "obec nebo město, kde místo leží (pokud je známé, jinak prázdné)",
  "lat": 50.1234,
  "lng": 14.5678,
  "category": "koupání",
  "tags": "outdoor,s dětmi,bazén",
  "summary": "2-3 věty popisující místo a proč je zajímavé."
}

Pravidla pro určení místa (DŮLEŽITÉ – v tomto pořadí priority):
1. NEJDŘÍV hledej konkrétní název místa/adresu v POPISKU (caption) – tvůrci tam místo často uvádějí, typicky za špendlíkem 📍, slovy "kde:", "místo:", nebo v hashtazích. Tohle je nejspolehlivější zdroj.
2. Pak TEXT ZOBRAZENÝ VE VIDEU (názvy míst, cedule, popisky na obrazovce).
3. Pak až mluvené slovo ve videu.
4. NIKDY si název místa nevymýšlej. Když místo nejde určit z žádného zdroje, dej do location_name "Neznámé místo" a lat/lng 0.

Další pravidla:
- category: jedna z: koupání, turistika, jídlo, kultura, příroda, sport, zábava, hotel, jiné
  (hotel = video je primárně o ubytování / hotelu / penzionu / kempu)
- lat/lng: odhadni co nejpřesnější souřadnice podle konkrétního názvu místa a adresy
- tags: max 4 tagy oddělené čárkou, bez mezer kolem čárek
- transcript: přepis mluveného slova z videa; pokud video nemá zvuk, nech prázdný řetězec"""


def analyze(media_path: str, url: str, yt_info: dict) -> VideoMetadata:
    """Send video to Gemini, get transcript + metadata in one call."""
    model = _get_model()
    author = yt_info.get("uploader") or yt_info.get("channel") or ""
    title = yt_info.get("title") or ""
    description = yt_info.get("description") or ""

    ext = os.path.splitext(media_path)[1].lower()
    mime = _VIDEO_MIME.get(ext, "video/mp4")
    media_file = genai.upload_file(media_path, mime_type=mime)

    # Video se po uploadu zpracovává; musíme počkat, než bude ACTIVE.
    waited = 0
    while media_file.state.name == "PROCESSING" and waited < 120:
        time.sleep(2)
        waited += 2
        media_file = genai.get_file(media_file.name)
    if media_file.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini nezpracoval video (stav {media_file.state.name})")

    prompt = f"""URL videa: {url}
Autor: {author}
Titulek: {title}

POPISEK VIDEA (caption – hlavní zdroj pro určení místa):
\"\"\"
{description[:2000]}
\"\"\"

Analyzuj přiložené video a extrahuj metadata o místě.
Místo urči především z popisku výše (často za 📍), pak z textu na obrazovce, pak z mluveného slova.
Pokud má video zvuk, přepiš mluvený projev do pole transcript."""

    response = model.generate_content(
        [media_file, SYSTEM_PROMPT + "\n\n" + prompt],
        generation_config=genai.GenerationConfig(
            temperature=0,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )

    try:
        raw = response.text.strip()
    except (ValueError, AttributeError) as e:
        # Gemini nevrátil textovou část (bezpečnostní blok, prázdná odpověď, MAX_TOKENS bez textu)
        raise RuntimeError(f"Gemini nevrátil žádný text k analýze ({e})")

    return parse_metadata(raw, url, author=author, title=title)


def strip_fences(raw: str) -> str:
    """Odstraní případné markdown fences (```json ... ```) kolem JSON odpovědi."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def parse_metadata(raw: str, url: str, author: str = "", title: str = "") -> VideoMetadata:
    """Převede JSON odpověď Gemini na VideoMetadata. Vyhazuje json.JSONDecodeError."""
    # JSON mód garantuje čistý JSON, ale pro jistotu odstraníme případné fences
    data = json.loads(strip_fences(raw))

    return VideoMetadata(
        url=url,
        author=author,
        title=title,
        location_name=data.get("location_name", ""),
        city=data.get("city", "") or "",
        lat=_safe_float(data.get("lat")),
        lng=_safe_float(data.get("lng")),
        category=data.get("category", "jiné"),
        tags=data.get("tags", ""),
        summary=data.get("summary", ""),
        transcript=data.get("transcript", ""),
        source=extract_source(url),
    )

import json
import os
import time
from google import genai
from google.genai import errors, types
from extractor import extract_source
from i18n import CATEGORIES, FALLBACK_CATEGORY, LANG, t
from models import VideoMetadata

GEMINI_MODEL = "gemini-3.6-flash"

_client = None


def _safe_float(v) -> float:
    """Safe conversion to float – Gemini may return null, empty or text."""
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _get_client() -> genai.Client:
    """Lazy init – Gemini is configured on first use, not at import time."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GEMINI_API_KEY environment variable")
        _client = genai.Client(api_key=api_key)
    return _client

_VIDEO_MIME = {
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".mkv": "video/x-matroska", ".m4v": "video/mp4", ".3gp": "video/3gpp",
}
_PHOTO_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
}

# The prompts are templates – tokens like __CATEGORIES__ are substituted via .replace()
# (str.format would clash with the braces of the example JSON).
_HOTEL_NOTE = {
    "cs": "\n  (hotel = video je primárně o ubytování / hotelu / penzionu / kempu)",
    "en": "\n  (hotel = the video is primarily about accommodation / a hotel / guesthouse / campsite)",
}

_SYSTEM_PROMPT_TEMPLATES = {
    "cs": """Jsi AI asistent, který analyzuje cestovní videa a fotky. Dostaneš samotné video nebo fotku, jeho popisek (caption) a URL.

Vrať POUZE validní JSON (bez markdown, bez dalšího textu) v tomto přesném formátu:
{
  "transcript": "plný přepis mluveného slova",
  "location_name": "název konkrétního místa (název objektu/atrakce)",
  "city": "obec nebo město, kde místo leží (pokud je známé, jinak prázdné)",
  "lat": 50.1234,
  "lng": 14.5678,
  "category": "__CATEGORY_EXAMPLE__",
  "tags": "outdoor,s dětmi,bazén",
  "summary": "2-3 věty popisující místo a proč je zajímavé."
}

Pravidla pro určení místa (DŮLEŽITÉ – v tomto pořadí priority):
1. NEJDŘÍV hledej konkrétní název místa/adresu v POPISKU (caption) – tvůrci tam místo často uvádějí, typicky za špendlíkem 📍, slovy "kde:", "místo:", nebo v hashtazích. Tohle je nejspolehlivější zdroj.
2. Pak TEXT ZOBRAZENÝ VE VIDEU NEBO NA FOTCE (názvy míst, cedule, popisky na obrazovce).
3. Pak až mluvené slovo ve videu (pokud jde o video).
4. NIKDY si název místa nevymýšlej. Když místo nejde určit z žádného zdroje, dej do location_name "Neznámé místo" a lat/lng 0.

Další pravidla:
- category: právě jedna z: __CATEGORIES____HOTEL_NOTE__
  Když žádná nesedí, použij "__FALLBACK__".
- lat/lng: odhadni co nejpřesnější souřadnice podle konkrétního názvu místa a adresy
- tags: max 4 tagy oddělené čárkou, bez mezer kolem čárek; piš je česky
- summary: piš česky
- transcript: přepis mluveného slova z videa v původním jazyce; u fotek a videí bez zvuku nech prázdný řetězec""",
    "en": """You are an AI assistant that analyzes travel videos and photos. You get the video or photo itself, its caption and URL.

Return ONLY valid JSON (no markdown, no extra text) in this exact format:
{
  "transcript": "full transcript of the spoken words",
  "location_name": "name of the specific place (name of the venue/attraction)",
  "city": "town or city where the place is located (if known, otherwise empty)",
  "lat": 50.1234,
  "lng": 14.5678,
  "category": "__CATEGORY_EXAMPLE__",
  "tags": "outdoor,kids,pool",
  "summary": "2-3 sentences describing the place and why it is interesting."
}

Rules for determining the place (IMPORTANT – in this order of priority):
1. FIRST look for a specific place name/address in the CAPTION – creators often state the place there, typically after a pin 📍, after words like "where:", "location:", or in hashtags. This is the most reliable source.
2. Then TEXT SHOWN IN THE VIDEO OR PHOTO (place names, signs, on-screen labels).
3. Only then the spoken words in the video (if it is a video).
4. NEVER make up a place name. If the place cannot be determined from any source, set location_name to "Unknown place" and lat/lng to 0.

Other rules:
- category: exactly one of: __CATEGORIES____HOTEL_NOTE__
  If none fits, use "__FALLBACK__".
- lat/lng: estimate the most precise coordinates based on the specific place name and address
- tags: max 4 comma-separated tags, no spaces around commas; write them in English
- summary: write in English
- transcript: transcript of the spoken words in their original language; for photos and videos without sound, leave an empty string""",
}

_USER_PROMPT_TEMPLATES = {
    "cs": '''URL videa: {url}
Autor: {author}
Titulek: {title}

POPISEK VIDEA (caption – hlavní zdroj pro určení místa):
"""
{description}
"""

Analyzuj přiložené video a extrahuj metadata o místě.
Místo urči především z popisku výše (často za 📍), pak z textu na obrazovce, pak z mluveného slova.
Pokud má video zvuk, přepiš mluvený projev do pole transcript.''',
    "en": '''Video URL: {url}
Author: {author}
Title: {title}

VIDEO CAPTION (the primary source for determining the place):
"""
{description}
"""

Analyze the attached video and extract metadata about the place.
Determine the place primarily from the caption above (often after 📍), then from on-screen text, then from the spoken words.
If the video has sound, transcribe the speech into the transcript field.''',
}

_USER_PROMPT_PHOTO_TEMPLATES = {
    "cs": '''URL příspěvku: {url}
Autor: {author}
Titulek: {title}

POPISEK PŘÍSPĚVKU (caption – hlavní zdroj pro určení místa):
"""
{description}
"""

Analyzuj přiloženou fotku a extrahuj metadata o místě.
Místo urči především z popisku výše (často za 📍), pak z toho, co je vidět na fotce (text, cedule, krajina, architektura).
Jde o fotku bez zvuku, pole transcript nech prázdné.''',
    "en": '''Post URL: {url}
Author: {author}
Title: {title}

POST CAPTION (the primary source for determining the place):
"""
{description}
"""

Analyze the attached photo and extract metadata about the place.
Determine the place primarily from the caption above (often after 📍), then from what is visible in the photo (text, signs, landscape, architecture).
This is a photo with no sound, leave the transcript field empty.''',
}


def system_prompt() -> str:
    """System prompt in the bot's language with the categories from the configuration."""
    hotel_note = _HOTEL_NOTE[LANG] if "hotel" in CATEGORIES else ""
    return (_SYSTEM_PROMPT_TEMPLATES[LANG]
            .replace("__CATEGORIES__", ", ".join(CATEGORIES))
            .replace("__CATEGORY_EXAMPLE__", CATEGORIES[0])
            .replace("__FALLBACK__", FALLBACK_CATEGORY)
            .replace("__HOTEL_NOTE__", hotel_note))


# Gemini occasionally answers 503 "currently experiencing high demand", and
# under batch/burst usage 429 "RESOURCE_EXHAUSTED" (free-tier rate limit) -
# both are transient, so retry with backoff instead of failing the whole
# video. Other 4xx errors (bad request, auth, ...) are not retried.
_RETRY_DELAYS_S = (20, 45, 60)


def _generate_with_retry(client: genai.Client, **kwargs):
    for delay in (*_RETRY_DELAYS_S, None):
        try:
            return client.models.generate_content(model=GEMINI_MODEL, **kwargs)
        except errors.ServerError:
            if delay is None:
                raise
            time.sleep(delay)
        except errors.ClientError as e:
            if delay is None or e.code != 429:
                raise
            time.sleep(delay)


def analyze(media_path: str, url: str, yt_info: dict) -> VideoMetadata:
    """Send video to Gemini, get transcript + metadata in one call."""
    client = _get_client()
    author = yt_info.get("uploader") or yt_info.get("channel") or ""
    title = yt_info.get("title") or ""
    description = yt_info.get("description") or ""

    ext = os.path.splitext(media_path)[1].lower()
    is_photo = ext in _PHOTO_MIME
    mime = _PHOTO_MIME[ext] if is_photo else _VIDEO_MIME.get(ext, "video/mp4")
    media_file = client.files.upload(
        file=media_path, config=types.UploadFileConfig(mime_type=mime))

    # The video is processed after upload; we have to wait until it is ACTIVE.
    waited = 0
    while media_file.state.name == "PROCESSING" and waited < 120:
        time.sleep(2)
        waited += 2
        media_file = client.files.get(name=media_file.name)
    if media_file.state.name != "ACTIVE":
        raise RuntimeError(t("gemini_not_processed", state=media_file.state.name))

    templates = _USER_PROMPT_PHOTO_TEMPLATES if is_photo else _USER_PROMPT_TEMPLATES
    prompt = templates[LANG].format(
        url=url, author=author, title=title, description=description[:2000])

    response = _generate_with_retry(
        client,
        contents=[media_file, system_prompt() + "\n\n" + prompt],
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )

    try:
        raw = response.text.strip()
    except (ValueError, AttributeError) as e:
        # Gemini returned no text part (safety block, empty response, MAX_TOKENS without text)
        raise RuntimeError(t("gemini_no_text", error=e))

    metadata = parse_metadata(raw, url, author=author, title=title)
    metadata.media_type = "photo" if is_photo else "video"
    return metadata


def strip_fences(raw: str) -> str:
    """Strip any markdown fences (```json ... ```) around the JSON response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def parse_metadata(raw: str, url: str, author: str = "", title: str = "") -> VideoMetadata:
    """Convert Gemini's JSON response to VideoMetadata. Raises json.JSONDecodeError."""
    # JSON mode guarantees clean JSON, but strip any fences just in case
    data = json.loads(strip_fences(raw))

    return VideoMetadata(
        url=url,
        author=author,
        title=title,
        location_name=data.get("location_name", ""),
        city=data.get("city", "") or "",
        lat=_safe_float(data.get("lat")),
        lng=_safe_float(data.get("lng")),
        category=data.get("category", FALLBACK_CATEGORY),
        tags=data.get("tags", ""),
        summary=data.get("summary", ""),
        transcript=data.get("transcript", ""),
        source=extract_source(url),
    )

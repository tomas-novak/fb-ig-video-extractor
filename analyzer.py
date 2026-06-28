import json
import os
import google.generativeai as genai
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

SYSTEM_PROMPT = """Jsi AI asistent, který analyzuje cestovní videa. Dostaneš přepis mluveného slova z videa, jeho popisek (caption) a URL.

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

Pravidla pro určení místa (DŮLEŽITÉ – v tomto pořadí priority):
1. NEJDŘÍV hledej konkrétní název místa/adresu v POPISKU (caption) – tvůrci tam místo často uvádějí, typicky za špendlíkem 📍, slovy "kde:", "místo:", nebo v hashtazích. Tohle je nejspolehlivější zdroj.
2. Pak až mluvené slovo v přepisu.
3. NIKDY si název místa nevymýšlej. Když místo není ani v popisku, ani v přepisu, dej do location_name "Neznámé místo" a lat/lng 0.

Další pravidla:
- category: jedna z: koupání, turistika, jídlo, kultura, příroda, sport, zábava, hotel, jiné
  (hotel = video je primárně o ubytování / hotelu / penzionu / kempu)
- lat/lng: odhadni co nejpřesnější souřadnice podle konkrétního názvu místa a adresy
- tags: max 4 tagy oddělené čárkou, bez mezer kolem čárek
- transcript: do tohoto pole dej POUZE mluvené slovo z audia, ne popisek"""


def analyze(audio_path: str, url: str, yt_info: dict) -> VideoMetadata:
    """Send audio to Gemini, get transcript + metadata in one call."""
    model = _get_model()
    author = yt_info.get("uploader") or yt_info.get("channel") or ""
    title = yt_info.get("title") or ""
    description = yt_info.get("description") or ""

    audio_file = genai.upload_file(audio_path, mime_type="audio/mp3")

    prompt = f"""URL videa: {url}
Autor: {author}
Titulek: {title}

POPISEK VIDEA (caption – hlavní zdroj pro určení místa):
\"\"\"
{description[:2000]}
\"\"\"

Přepiš mluvený projev z přiloženého audia a extrahuj metadata o místě.
Místo urči především z popisku výše (často za 📍), audio použij jen doplňkově."""

    response = model.generate_content(
        [audio_file, SYSTEM_PROMPT + "\n\n" + prompt],
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
        lat=_safe_float(data.get("lat")),
        lng=_safe_float(data.get("lng")),
        category=data.get("category", "jiné"),
        tags=data.get("tags", ""),
        summary=data.get("summary", ""),
        transcript=data.get("transcript", ""),
        source=source,
    )

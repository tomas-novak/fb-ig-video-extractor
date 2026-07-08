import asyncio
import os
import secrets
import sys
import httpx
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

load_dotenv()

from extractor import download_media, ffmpeg_diagnostics
from analyzer import analyze
from sheets import (append_row, read_rows, set_group_ids, new_group_id,
                    find_duplicate, set_visited, delete_place_rows, find_by_place_id)
from geocoder import geocode, maps_link, distance_km
from dedup import find_duplicates
from map_page import MAP_HTML

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Čárkou oddělená Telegram user ID, která smí bota používat. Prázdné = kdokoliv.
def _parse_allowed_users(raw: str) -> set[int]:
    """Fail closed: neplatná položka (překlep, @username...) je chyba konfigurace –
    radši spadnout při startu než tiše zpřístupnit bota všem."""
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    invalid = [t for t in tokens if not t.isdigit()]
    if invalid:
        raise ValueError(
            f"TELEGRAM_ALLOWED_USERS obsahuje neplatné položky {invalid} – "
            "očekávám číselná Telegram user ID oddělená čárkou (zjistíš příkazem /id)"
        )
    return {int(t) for t in tokens}


ALLOWED_USERS = _parse_allowed_users(os.getenv("TELEGRAM_ALLOWED_USERS", ""))


def is_authorized(user_id: int | None) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


def is_command(text: str, cmd: str) -> bool:
    """Přesná shoda příkazu: '/id' i '/id@NazevBota', ale ne '/idea'."""
    parts = text.split()
    first = parts[0].lower() if parts else ""
    return first == cmd or first.startswith(cmd + "@")


# Token chránící mapová data (/data, /visited, /delete). Prázdné = mapa veřejná.
MAP_TOKEN = os.getenv("MAP_TOKEN", "")
# Volitelný read-only token pro sdílení mapy (jen prohlížení, žádné mazání/visited).
MAP_VIEW_TOKEN = os.getenv("MAP_VIEW_TOKEN", "")


def _token_matches(supplied: str, expected: str) -> bool:
    # encode: compare_digest se str argumenty vyžaduje ASCII – ne-ASCII vstup
    # by shodil 500 místo čistého 403
    return bool(expected) and secrets.compare_digest(supplied.encode(), expected.encode())


def check_map_token(request: Request, write: bool = True) -> None:
    """Ověří ?token= v URL. write=True vyžaduje hlavní MAP_TOKEN,
    write=False pustí i read-only MAP_VIEW_TOKEN. Bez MAP_TOKEN je vše veřejné."""
    if not MAP_TOKEN:
        return
    supplied = request.query_params.get("token", "")
    if _token_matches(supplied, MAP_TOKEN):
        return
    if not write and _token_matches(supplied, MAP_VIEW_TOKEN):
        return
    raise HTTPException(status_code=403, detail="invalid or missing map token")


def can_edit_map(request: Request) -> bool:
    """True, když má požadavek plná práva (mazání, visited)."""
    if not MAP_TOKEN:
        return True
    return _token_matches(request.query_params.get("token", ""), MAP_TOKEN)


def _public_url() -> str:
    """Veřejná adresa instance: PUBLIC_URL, nebo automaticky z Railway."""
    explicit = os.getenv("PUBLIC_URL", "").rstrip("/")
    if explicit:
        return explicit
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    return f"https://{railway_domain}" if railway_domain else ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-registrace Telegram webhooku – odpadá ruční krok při nasazení.
    # Chyba nesmí zabránit startu (Telegram může být chvíli nedostupný).
    url = _public_url()
    if url:
        try:
            await set_webhook(url)
        except Exception as e:
            print(f"[webhook] auto-registrace selhala: {type(e).__name__}: {e}")
    else:
        print("[webhook] PUBLIC_URL ani RAILWAY_PUBLIC_DOMAIN není nastaveno – "
              "webhook zaregistruj ručně: python main.py --set-webhook <url>")
    yield


app = FastAPI(lifespan=lifespan)

# Drží silné reference na běžící background tasky, aby je GC nesebral uprostřed běhu.
_background_tasks: set = set()


async def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json=payload)


async def answer_callback(callback_id: str, text: str = "") -> None:
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
            "callback_query_id": callback_id,
            "text": text,
        })


def is_valid_url(text: str) -> bool:
    text = text.strip()
    return text.startswith("http://") or text.startswith("https://")


def friendly_error(err: str) -> str:
    """Přeloží technickou chybu na srozumitelnou hlášku pro uživatele."""
    low = err.lower()
    if "no video formats" in low or "no video" in low:
        return ("📷 Tohle vypadá jako fotka nebo série fotek (carousel), ne video. "
                "Pošli mi prosím odkaz na video nebo reel.")
    if "empty media response" in low or "login required" in low or "rate-limit" in low \
            or "unable to extract" in low or "checkpoint" in low or "challenge" in low:
        return ("🔒 Nepodařilo se dostat k obsahu (Instagram nejspíš vyžaduje přihlášení "
                "nebo vypršely cookies). U Facebook odkazů to funguje vždy.")
    if "unsupported url" in low or "unsupported" in low:
        return "🤔 Tenhle odkaz neumím zpracovat. Podporuju Facebook a Instagram videa/reels."
    if "audio codec" in low or "ffprobe" in low or "requested format" in low:
        return ("🔇 Z videa se nepodařilo získat zvukovou stopu (možná nemá zvuk). "
                "Zkus prosím jiné video.")
    return f"❌ Něco se nepovedlo: {err[:200]}"


@app.post("/webhook")
async def webhook(request: Request):
    # Volitelné ověření secret tokenu
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret")

    update = await request.json()

    # Odpověď na tlačítka Sloučit/Ponechat u návrhů duplikátů
    callback = update.get("callback_query")
    if callback:
        if not is_authorized((callback.get("from") or {}).get("id")):
            # odpovědět prázdně, ať cizímu uživateli nevisí "točící se" tlačítko
            await answer_callback(callback["id"])
            return {"ok": True}
        task = asyncio.create_task(handle_callback(callback))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}

    message = update.get("message") or update.get("channel_post")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    user_id = (message.get("from") or {}).get("id")

    # /id funguje pro každého – potřebné pro prvotní nastavení whitelistu
    if is_command(text, "/id") and user_id is not None:
        await send_message(chat_id, f"🆔 Tvoje Telegram user ID: {user_id}")
        return {"ok": True}

    if not is_authorized(user_id):
        if user_id is not None:
            await send_message(chat_id, "⛔ Tento bot je soukromý. Pokud je tvůj, přidej si "
                                        f"svoje ID ({user_id}) do TELEGRAM_ALLOWED_USERS.")
        # channel_post bez odesílatele při zapnutém whitelistu tiše ignorovat
        return {"ok": True}

    # Poslaná poloha -> nejbližší uložená místa
    location = message.get("location")
    if location and "latitude" in location:
        task = asyncio.create_task(
            handle_location(chat_id, location["latitude"], location["longitude"]))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}

    # Příkaz: fulltextové hledání v uložených místech
    if is_command(text, "/hledej"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await send_message(chat_id, "Použití: /hledej <text>\nnapř. /hledej tobogán")
            return {"ok": True}
        task = asyncio.create_task(handle_search(chat_id, parts[1].strip()))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}

    # Příkaz: kontrola duplicitních míst
    if is_command(text, "/zkontroluj"):
        await send_message(chat_id, "🔍 Kontroluji duplicitní místa, chvíli počkej...")
        task = asyncio.create_task(run_dedup_check(chat_id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}

    if not is_valid_url(text):
        await send_message(chat_id, "Pošli mi URL Facebook nebo Instagram Reels videa.\n"
                                    "📎 Pošli mi svoji polohu a najdu uložená místa poblíž.\n"
                                    "/hledej <text> – hledání v uložených místech\n"
                                    "/zkontroluj – kontrola duplicitních míst")
        return {"ok": True}

    # Zpracování v background tasku aby webhook rychle odpověděl.
    # Referenci držíme v _background_tasks, jinak ji může GC sebrat uprostřed běhu.
    task = asyncio.create_task(process_video(chat_id, text))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"ok": True}


async def process_video(chat_id: int, url: str) -> None:
    media_path = None
    try:
        # 1) Rychlá kontrola duplicity podle URL (před stahováním, zdarma)
        dup = await asyncio.to_thread(find_duplicate, url)
        if dup:
            await send_message(chat_id, f"⚠️ Tohle video už máš uložené:\n"
                                        f"📍 {dup['location_name']} ({dup['date']})")
            return

        await send_message(chat_id, "⏳ Zpracovávám video, chvíli počkej...")

        # 2) Stažení videa
        media_path, yt_info = await asyncio.to_thread(download_media, url)

        # 3) Kontrola duplicity podle ID videa (chytí i jiný tvar odkazu na totéž video)
        video_id = str(yt_info.get("id") or "")
        if video_id:
            dup = await asyncio.to_thread(find_duplicate, "", video_id)
            if dup:
                await send_message(chat_id, f"⚠️ Tohle video už máš uložené (pod jiným odkazem):\n"
                                            f"📍 {dup['location_name']} ({dup['date']})")
                return

        # 4) Analýza přes Gemini
        metadata = await asyncio.to_thread(analyze, media_path, url, yt_info)
        metadata.video_id = video_id

        # 5) Geokódování: přesné souřadnice + place_id + odkaz na Google Maps
        geo = await asyncio.to_thread(geocode, metadata.location_name, metadata.city)
        if geo:
            metadata.lat = geo["lat"]
            metadata.lng = geo["lng"]
            metadata.place_id = geo["place_id"]
            metadata.maps_url = geo["maps_url"]
            metadata.geo_source = "places"
        else:
            metadata.maps_url = maps_link(name=metadata.location_name)
            metadata.geo_source = "gemini"

        # 6) Stejné místo (place_id) už existuje? -> rovnou do stejné skupiny
        group_note = ""
        if metadata.place_id:
            match = await asyncio.to_thread(find_by_place_id, metadata.place_id)
            if match:
                group = match["group_id"] or new_group_id()
                if not match["group_id"]:
                    await asyncio.to_thread(set_group_ids, {match["row"]: group})
                metadata.group_id = group
                group_note = f"\n🔗 Přidáno k existujícímu místu „{match['location_name']}“."

        # 7) Uložení do Sheets
        await asyncio.to_thread(append_row, metadata)

        # 8) Odpověď uživateli
        precision = "" if metadata.geo_source == "places" else "\n⚠️ Poloha je jen odhad (místo se nepodařilo najít na Google Maps)."
        reply = (
            f"✅ Uloženo!\n"
            f"📍 {metadata.location_name}\n"
            f"🏷️ {metadata.category} | {metadata.tags}\n\n"
            f"{metadata.summary}\n"
            f"🧭 {metadata.maps_url}"
            f"{precision}{group_note}"
        )
        await send_message(chat_id, reply)

    except Exception as e:
        await send_message(chat_id, friendly_error(str(e)))
    finally:
        if media_path and os.path.exists(media_path):
            try:
                os.remove(media_path)
                os.rmdir(os.path.dirname(media_path))
            except OSError:
                pass


NEARBY_RADIUS_KM = 50
NEARBY_LIMIT = 5
SEARCH_LIMIT = 5


def _fold(s: str) -> str:
    """lowercase + odstranění diakritiky ('Hřiště' -> 'hriste')."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if not unicodedata.combining(c))


def search_places(places: list[dict], query: str) -> list[dict]:
    """Fulltext v názvu (váha 3), tazích (2) a shrnutí (1). Skupiny jednou."""
    q = _fold(query.strip())
    if not q:
        return []
    groups: dict[str, list[dict]] = {}
    for p in places:
        key = p["group_id"] or f"solo-{p['row']}"
        groups.setdefault(key, []).append(p)

    scored = []
    for group in groups.values():
        rep = group[0]
        score = 0
        # Sloučené řádky mohou mít různé varianty názvu – hledat ve všech
        if any(q in _fold(p["location_name"]) for p in group):
            score += 3
        if any(q in _fold(p["tags"]) for p in group):
            score += 2
        if any(q in _fold(p["summary"]) for p in group):
            score += 1
        if score:
            rep = rep | {"visited": any(p["visited"] for p in group)}
            scored.append((score, rep))
    scored.sort(key=lambda x: -x[0])
    return [rep for _, rep in scored[:SEARCH_LIMIT]]


async def handle_search(chat_id: int, query: str) -> None:
    try:
        places = await asyncio.to_thread(read_rows)
        hits = search_places(places, query)
        if not hits:
            await send_message(chat_id, f"🔍 Pro „{query}“ jsem nic nenašel.")
            return
        lines = [f"🔍 Nalezeno pro „{query}“:", ""]
        for p in hits:
            mark = " ✅" if p["visited"] else ""
            url = p["maps_url"] or maps_link(name=p["location_name"])
            lines.append(f"• {p['location_name']} ({p['category']}){mark}")
            lines.append(f"  🧭 {url}")
        await send_message(chat_id, "\n".join(lines))
    except Exception as e:
        await send_message(chat_id, f"❌ Hledání selhalo: {type(e).__name__}: {e}")


def nearest_places(places: list[dict], lat: float, lng: float) -> list[tuple[float, dict]]:
    """Nenavštívená místa seřazená podle vzdálenosti od dané polohy.
    Sloučené skupiny (group_id) počítá jednou. Vrací [(vzdálenost_km, místo), ...]."""
    groups: dict[str, list[dict]] = {}
    for p in places:
        key = p["group_id"] or f"solo-{p['row']}"
        groups.setdefault(key, []).append(p)

    result = []
    for group in groups.values():
        if any(p["visited"] for p in group):
            continue
        # Řádky skupiny mohou mít různé souřadnice (např. sloučení dvou odhadů) –
        # reprezentantem je záznam nejblíž k uživateli, ne group[0]
        rep = min(group, key=lambda p: distance_km(lat, lng, p["lat"], p["lng"]))
        result.append((distance_km(lat, lng, rep["lat"], rep["lng"]), rep))
    result.sort(key=lambda x: x[0])
    return result


async def handle_location(chat_id: int, lat: float, lng: float) -> None:
    """Odpoví seznamem nejbližších uložených (nenavštívených) míst."""
    try:
        places = await asyncio.to_thread(read_rows)
        ranked = nearest_places(places, lat, lng)
        if not ranked:
            await send_message(chat_id, "Nemáš uložená žádná nenavštívená místa.")
            return

        nearby = [(d, p) for d, p in ranked if d <= NEARBY_RADIUS_KM][:NEARBY_LIMIT]
        if not nearby:
            d, p = ranked[0]
            url = p["maps_url"] or maps_link(name=p["location_name"])
            await send_message(chat_id, f"V okruhu {NEARBY_RADIUS_KM} km nemáš nic uloženo. "
                                        f"Nejblíž je:\n📍 {p['location_name']} ({d:.0f} km)\n🧭 {url}")
            return

        lines = [f"📍 Nejbližší uložená místa ({len(nearby)}):", ""]
        for d, p in nearby:
            url = p["maps_url"] or maps_link(name=p["location_name"])
            dist = f"{d:.1f} km" if d < 10 else f"{d:.0f} km"
            lines.append(f"• {p['location_name']} – {dist} ({p['category']})")
            lines.append(f"  🧭 {url}")
        await send_message(chat_id, "\n".join(lines))
    except Exception as e:
        await send_message(chat_id, f"❌ Hledání selhalo: {type(e).__name__}: {e}")


async def run_dedup_check(chat_id: int) -> None:
    """Najde podezřelé duplikáty (Claude) a pošle návrhy s tlačítky Sloučit/Ponechat."""
    try:
        places = await asyncio.to_thread(read_rows)
        suggestions = await asyncio.to_thread(find_duplicates, places)

        if not suggestions:
            await send_message(chat_id, "✅ Žádné duplicitní místo jsem nenašel.")
            return

        for s in suggestions:
            a, b = s["a"], s["b"]
            text = (
                f"🤔 Vypadá to na stejné místo:\n\n"
                f"1️⃣ {a['location_name']} ({a['date']})\n"
                f"2️⃣ {b['location_name']} ({b['date']})\n\n"
                f"📏 Vzdálenost: {s['distance_km']:.1f} km\n"
                f"💡 {s['reason']}"
            )
            keyboard = {"inline_keyboard": [[
                {"text": "🔗 Sloučit", "callback_data": f"merge:{a['row']}:{b['row']}"},
                {"text": "✋ Ponechat zvlášť", "callback_data": "keep"},
            ]]}
            await send_message(chat_id, text, reply_markup=keyboard)

        await send_message(chat_id, f"Hotovo – {len(suggestions)} návrh(ů) výše. Rozhodni tlačítky.")
    except Exception as e:
        await send_message(chat_id, f"❌ Kontrola selhala: {type(e).__name__}: {e}")


async def handle_callback(callback: dict) -> None:
    """Zpracuje kliknutí na tlačítko Sloučit/Ponechat."""
    callback_id = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data") or ""

    try:
        if data == "keep":
            await answer_callback(callback_id, "Ponecháno zvlášť")
            await send_message(chat_id, "✋ OK, nechávám jako dvě různá místa.")
            return

        if data.startswith("merge:"):
            _, row_a, row_b = data.split(":")
            row_a, row_b = int(row_a), int(row_b)

            # Sloučení = oběma řádkům stejné group_id (zachová existující skupinu, jinak nová)
            places = await asyncio.to_thread(read_rows)
            by_row = {p["row"]: p for p in places}
            a, b = by_row.get(row_a), by_row.get(row_b)
            if not a or not b:
                await answer_callback(callback_id, "Řádek už neexistuje")
                await send_message(chat_id, "⚠️ Některý z řádků už v tabulce není (možná smazán). Spusť /zkontroluj znovu.")
                return

            group = a["group_id"] or b["group_id"] or new_group_id()
            await asyncio.to_thread(set_group_ids, {row_a: group, row_b: group})
            await answer_callback(callback_id, "Sloučeno")
            await send_message(chat_id, f"🔗 Sloučeno: „{a['location_name']}“ + „{b['location_name']}“ se teď na mapě zobrazí jako jedno místo.")
            return

        await answer_callback(callback_id)
    except Exception as e:
        await answer_callback(callback_id, "Chyba")
        await send_message(chat_id, f"❌ Sloučení selhalo: {type(e).__name__}: {e}")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug")
async def debug(request: Request):
    check_map_token(request)
    return ffmpeg_diagnostics()


@app.get("/data")
async def data(request: Request):
    check_map_token(request, write=False)
    try:
        places = await asyncio.to_thread(read_rows)
        # Mapa podle hlavičky pozná, zda smí ukázat tlačítka mazání/visited
        headers = {"X-Can-Edit": "1" if can_edit_map(request) else "0"}
        return JSONResponse(places, headers=headers)
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


def _export_places(places: list[dict]) -> list[dict]:
    """Jedno místo na skupinu (group_id), stejně jako na mapě.
    Stav navštíveno se agreguje přes celou skupinu (shodně s mapou)."""
    groups: dict[str, list[dict]] = {}
    for p in places:
        key = p["group_id"] or f"solo-{p['row']}"
        groups.setdefault(key, []).append(p)
    return [g[0] | {
        "urls": [x["url"] for x in g if x["url"]],
        "visited": any(x["visited"] for x in g),
    } for g in groups.values()]


def _build_export(places: list[dict], fmt: str) -> tuple[str, str, str]:
    """Vrátí (obsah, media_type, přípona) pro geojson/gpx/kml."""
    import json as _json
    from xml.sax.saxutils import escape

    items = _export_places(places)

    if fmt == "geojson":
        features = [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p["lng"], p["lat"]]},
            "properties": {
                "name": p["location_name"], "category": p["category"],
                "tags": p["tags"], "summary": p["summary"],
                "visited": p["visited"], "videos": p["urls"],
                "maps_url": p["maps_url"],
            },
        } for p in items]
        content = _json.dumps({"type": "FeatureCollection", "features": features},
                              ensure_ascii=False, indent=2)
        return content, "application/geo+json", "geojson"

    def desc(p):
        parts = [p["category"]]
        if p["tags"]:
            parts.append(p["tags"])
        if p["summary"]:
            parts.append(p["summary"])
        parts += p["urls"]
        return escape(" | ".join(parts))

    if fmt == "gpx":
        wpts = "\n".join(
            f'  <wpt lat="{p["lat"]}" lon="{p["lng"]}">\n'
            f'    <name>{escape(p["location_name"])}</name>\n'
            f'    <desc>{desc(p)}</desc>\n'
            f'  </wpt>' for p in items)
        content = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<gpx version="1.1" creator="fb-ig-video-extractor" '
                   'xmlns="http://www.topografix.com/GPX/1/1">\n'
                   f'{wpts}\n</gpx>\n')
        return content, "application/gpx+xml", "gpx"

    if fmt == "kml":
        marks = "\n".join(
            f'    <Placemark>\n'
            f'      <name>{escape(p["location_name"])}</name>\n'
            f'      <description>{desc(p)}</description>\n'
            f'      <Point><coordinates>{p["lng"]},{p["lat"]}</coordinates></Point>\n'
            f'    </Placemark>' for p in items)
        content = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<kml xmlns="http://www.opengis.net/kml/2.2">\n  <Document>\n'
                   f'    <name>Výlety</name>\n{marks}\n  </Document>\n</kml>\n')
        return content, "application/vnd.google-earth.kml+xml", "kml"

    raise HTTPException(status_code=400, detail="format must be geojson, gpx or kml")


@app.get("/export")
async def export(request: Request, format: str = "geojson"):
    """Export míst pro import do Mapy.cz, Organic Maps, Google My Maps..."""
    check_map_token(request, write=False)
    places = await asyncio.to_thread(read_rows)
    content, media_type, ext = _build_export(places, format.lower())
    from fastapi.responses import Response
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="vylety.{ext}"'})


@app.post("/visited")
async def visited(request: Request):
    """Označí místa (řádky) jako navštívená/nenavštívená – volá mapa."""
    check_map_token(request)
    try:
        data = await request.json()
        rows = [int(r) for r in data.get("rows", [])]
        flag = bool(data.get("visited"))
        if not rows:
            return JSONResponse({"error": "no rows"}, status_code=400)
        await asyncio.to_thread(set_visited, rows, flag)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


@app.post("/delete")
async def delete_place(request: Request):
    """Smaže místo (řádky) z tabulky – volá mapa po dvoufázovém potvrzení."""
    check_map_token(request)
    try:
        data = await request.json()
        rows = [int(r) for r in data.get("rows", [])]
        if not rows:
            return JSONResponse({"error": "no rows"}, status_code=400)
        await asyncio.to_thread(delete_place_rows, rows)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


@app.get("/map", response_class=HTMLResponse)
async def map_view():
    return HTMLResponse(MAP_HTML)


# Registrace webhooku (volá se automaticky při startu, ručně přes --set-webhook)
async def set_webhook(public_url: str):
    url = f"{TELEGRAM_API}/setWebhook"
    params = {"url": f"{public_url}/webhook"}
    if WEBHOOK_SECRET:
        params["secret_token"] = WEBHOOK_SECRET
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=params)
        print(f"[webhook] setWebhook {public_url}/webhook -> {r.json()}")


if __name__ == "__main__":
    if "--set-webhook" in sys.argv:
        idx = sys.argv.index("--set-webhook")
        public_url = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else input("Public URL: ")
        asyncio.run(set_webhook(public_url))
    else:
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)

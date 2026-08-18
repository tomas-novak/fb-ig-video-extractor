import asyncio
import os
import secrets
import sys
import unicodedata
import httpx
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

load_dotenv()

from extractor import download_media, ffmpeg_diagnostics
from analyzer import analyze
from i18n import t, command_aliases, command_name, help_text, menu_commands
from sheets import (append_row, read_rows, set_group_ids, new_group_id,
                    find_duplicate, set_visited, delete_place_rows, find_by_place_id)
from geocoder import geocode, maps_link, distance_km
from thumbnails import thumbnail_path, save_thumbnail
from dedup import find_duplicates
from map_page import render_map
from landing_page import LANDING_HTML

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Comma-separated Telegram user IDs allowed to use the bot. Empty = anyone.
def _parse_allowed_users(raw: str) -> set[int]:
    """Fail closed: an invalid item (typo, @username...) is a configuration error –
    better to crash at startup than to quietly expose the bot to everyone."""
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    invalid = [t for t in tokens if not t.isdigit()]
    if invalid:
        raise ValueError(
            f"TELEGRAM_ALLOWED_USERS contains invalid items {invalid} – "
            "expected comma-separated numeric Telegram user IDs (get yours via /id)"
        )
    return {int(t) for t in tokens}


ALLOWED_USERS = _parse_allowed_users(os.getenv("TELEGRAM_ALLOWED_USERS", ""))


def is_authorized(user_id: int | None) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


def is_command(text: str, *cmds: str) -> bool:
    """Exact command match: '/id' and '/id@BotName', but not '/idea'.
    Multiple names = aliases (Czech and English commands always both work)."""
    parts = text.split()
    first = parts[0].lower() if parts else ""
    return any(first == cmd or first.startswith(cmd + "@") for cmd in cmds)


# Token protecting the map data (/data, /visited, /delete). Empty = public map.
MAP_TOKEN = os.getenv("MAP_TOKEN", "")
# Optional read-only token for sharing the map (view only, no deleting/visited).
MAP_VIEW_TOKEN = os.getenv("MAP_VIEW_TOKEN", "")

# Fail closed: a view token without the main token would quietly leave the map fully public.
if MAP_VIEW_TOKEN and not MAP_TOKEN:
    raise ValueError("MAP_VIEW_TOKEN is set without MAP_TOKEN – the map would stay "
                     "public. Set MAP_TOKEN as well, or remove MAP_VIEW_TOKEN.")
if MAP_VIEW_TOKEN and MAP_VIEW_TOKEN == MAP_TOKEN:
    print("[config] WARNING: MAP_VIEW_TOKEN equals MAP_TOKEN – the shared link "
          "has full permissions including deletion. Pick a different value.")


def _token_matches(supplied: str, expected: str) -> bool:
    # encode: compare_digest with str arguments requires ASCII – non-ASCII input
    # would raise a 500 instead of a clean 403
    return bool(expected) and secrets.compare_digest(supplied.encode(), expected.encode())


def check_map_token(request: Request, write: bool = True) -> None:
    """Verify ?token= in the URL. write=True requires the main MAP_TOKEN,
    write=False also accepts the read-only MAP_VIEW_TOKEN. Without MAP_TOKEN everything is public."""
    if not MAP_TOKEN:
        return
    supplied = request.query_params.get("token", "")
    if _token_matches(supplied, MAP_TOKEN):
        return
    if not write and _token_matches(supplied, MAP_VIEW_TOKEN):
        return
    raise HTTPException(status_code=403, detail="invalid or missing map token")


def can_edit_map(request: Request) -> bool:
    """True when the request has full permissions (deleting, visited)."""
    if not MAP_TOKEN:
        return True
    return _token_matches(request.query_params.get("token", ""), MAP_TOKEN)


def _public_url() -> str:
    """Public address of the instance: PUBLIC_URL, or automatically from Railway."""
    explicit = os.getenv("PUBLIC_URL", "").rstrip("/")
    if explicit:
        return explicit
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    return f"https://{railway_domain}" if railway_domain else ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-registration of the Telegram webhook – removes a manual deployment step.
    # A failure must not prevent startup (Telegram may be briefly unavailable).
    url = _public_url()
    if url:
        try:
            await set_webhook(url)
        except Exception as e:
            print(f"[webhook] auto-registration failed: {type(e).__name__}: {e}")
    else:
        print("[webhook] neither PUBLIC_URL nor RAILWAY_PUBLIC_DOMAIN is set – "
              "register the webhook manually: python main.py --set-webhook <url>")
    try:
        await set_my_commands()
    except Exception as e:
        print(f"[commands] setMyCommands failed: {type(e).__name__}: {e}")
    yield
    await close_telegram_client()


app = FastAPI(lifespan=lifespan)

# Holds strong references to running background tasks so the GC does not collect them mid-run.
_background_tasks: set = set()


# Shared HTTP client for the Telegram API – created lazily on first call
# (so CLI --set-webhook works outside the lifespan too), closed on shutdown.
_telegram_client: httpx.AsyncClient | None = None


def _get_telegram_client() -> httpx.AsyncClient:
    global _telegram_client
    if _telegram_client is None or _telegram_client.is_closed:
        _telegram_client = httpx.AsyncClient()
    return _telegram_client


async def close_telegram_client() -> None:
    if _telegram_client is not None and not _telegram_client.is_closed:
        await _telegram_client.aclose()


async def telegram_call(method: str, payload: dict) -> dict:
    """The single place for calling the Telegram Bot API – timeouts, retries etc.
    are changed here if needed, not in the individual wrappers.

    The response body never raises: neither a non-JSON body (e.g. an HTML 502
    from a proxy) nor {"ok": false} may crash the webhook handler – it is logged
    and returned to the caller. Network errors (timeout, dropped connection)
    still propagate as before."""
    r = await _get_telegram_client().post(f"{TELEGRAM_API}/{method}", json=payload)
    try:
        result = r.json()
    except ValueError:
        result = {"ok": False, "error": f"non-JSON response (HTTP {r.status_code})"}
    if not result.get("ok"):
        print(f"[telegram] {method} failed: {result}")
    return result


async def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await telegram_call("sendMessage", payload)


async def answer_callback(callback_id: str, text: str = "") -> None:
    await telegram_call("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
    })


def is_valid_url(text: str) -> bool:
    text = text.strip()
    return text.startswith("http://") or text.startswith("https://")


def friendly_error(err: str) -> str:
    """Translate a technical error into a message the user can understand."""
    low = err.lower()
    if "no video formats" in low or "no video" in low:
        return t("err_photo")
    if "empty media response" in low or "login required" in low or "rate-limit" in low \
            or "unable to extract" in low or "checkpoint" in low or "challenge" in low:
        return t("err_login")
    if "unsupported url" in low or "unsupported" in low:
        return t("err_unsupported")
    # matches err_video_too_long in both languages – "příliš dlouhé" is the Czech wording
    if "příliš dlouhé" in low or "too long" in low:
        return t("err_too_long", err=err)
    if "sign in to confirm" in low or "not a bot" in low:
        return t("err_youtube_bot")
    if "audio codec" in low or "ffprobe" in low or "requested format" in low:
        return t("err_no_audio")
    return t("err_generic", err=err[:200])


@app.post("/webhook")
async def webhook(request: Request):
    # Optional secret token verification
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret")

    update = await request.json()

    # Response to the Merge/Keep buttons on duplicate suggestions
    callback = update.get("callback_query")
    if callback:
        if not is_authorized((callback.get("from") or {}).get("id")):
            # answer with nothing so an outside user is not left with a "spinning" button
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

    # /id works for everyone – needed for the initial whitelist setup
    if is_command(text, *command_aliases("id")) and user_id is not None:
        await send_message(chat_id, t("id_reply", user_id=user_id))
        return {"ok": True}

    if not is_authorized(user_id):
        if user_id is not None:
            await send_message(chat_id, t("private_bot", user_id=user_id))
        # silently ignore a channel_post without a sender when the whitelist is on
        return {"ok": True}

    # Command: help (also sent as a reply to any non-URL text below)
    if is_command(text, *command_aliases("help")):
        await send_message(chat_id, help_text())
        return {"ok": True}

    # Shared location -> closest saved places
    location = message.get("location")
    if location and "latitude" in location:
        task = asyncio.create_task(
            handle_location(chat_id, location["latitude"], location["longitude"]))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}

    # Command: full-text search in saved places
    if is_command(text, *command_aliases("search")):
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await send_message(chat_id, t("search_usage", cmd=command_name("search")))
            return {"ok": True}
        task = asyncio.create_task(handle_search(chat_id, parts[1].strip()))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}

    # Command: duplicate place check
    if is_command(text, *command_aliases("dedup")):
        await send_message(chat_id, t("dedup_started"))
        task = asyncio.create_task(run_dedup_check(chat_id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}

    if not is_valid_url(text):
        await send_message(chat_id, help_text())
        return {"ok": True}

    # Processed in a background task so the webhook responds quickly.
    # The reference is kept in _background_tasks, otherwise the GC could collect it mid-run.
    task = asyncio.create_task(process_video(chat_id, text))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"ok": True}


async def process_video(chat_id: int, url: str) -> None:
    media_path = None
    try:
        # 1) Quick duplicate check by URL (before downloading, free)
        dup = await asyncio.to_thread(find_duplicate, url)
        if dup:
            await send_message(chat_id, t("dup_saved", name=dup["location_name"],
                                          date=dup["date"]))
            return

        await send_message(chat_id, t("processing"))

        # 2) Download the video
        media_path, yt_info = await asyncio.to_thread(download_media, url)

        # 3) Duplicate check by video ID (also catches a different link form of the same video)
        video_id = str(yt_info.get("id") or "")
        if video_id:
            dup = await asyncio.to_thread(find_duplicate, "", video_id)
            if dup:
                await send_message(chat_id, t("dup_saved_other", name=dup["location_name"],
                                              date=dup["date"]))
                return

        # 4) Analysis via Gemini
        metadata = await asyncio.to_thread(analyze, media_path, url, yt_info)
        metadata.video_id = video_id

        # 5) Geocoding: exact coordinates + place_id + Google Maps link
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

        # 6) Does the same place (place_id) already exist? -> put it straight into the same group
        group_note = ""
        if metadata.place_id:
            match = await asyncio.to_thread(find_by_place_id, metadata.place_id)
            if match:
                group = match["group_id"] or new_group_id()
                if not match["group_id"]:
                    await asyncio.to_thread(set_group_ids, {match["row"]: group})
                metadata.group_id = group
                group_note = t("group_note", name=match["location_name"])

        # 7) Save to Sheets
        row = await asyncio.to_thread(append_row, metadata)

        # 7b) Cache a small preview image for the map popup (best-effort;
        # never raises - see thumbnails.py). Photos use the file we already
        # downloaded; videos use yt-dlp's own poster frame; anything else
        # falls back to a Places Photo of the geocoded place, if any.
        thumb_url = yt_info.get("thumbnail") or next(
            (t.get("url") for t in reversed(yt_info.get("thumbnails") or [])), None)
        source_path = media_path if metadata.media_type == "photo" else None
        photo_name = geo.get("photo_name", "") if geo else ""
        await asyncio.to_thread(
            save_thumbnail, row, source_path=source_path,
            thumb_url=thumb_url, photo_name=photo_name)

        # 8) Reply to the user
        precision = "" if metadata.geo_source == "places" else t("precision_note")
        reply = t("saved", name=metadata.location_name, category=metadata.category,
                  tags=metadata.tags, summary=metadata.summary,
                  maps_url=metadata.maps_url, precision=precision, group_note=group_note)
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
    """lowercase + diacritics removal ('Hřiště' -> 'hriste')."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if not unicodedata.combining(c))


def search_places(places: list[dict], query: str) -> list[dict]:
    """Full-text over the name (weight 3), tags (2) and summary (1). Groups counted once."""
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
        # Merged rows may carry different name variants – search all of them
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
            await send_message(chat_id, t("search_none", query=query))
            return
        lines = [t("search_header", query=query), ""]
        for p in hits:
            mark = " ✅" if p["visited"] else ""
            url = p["maps_url"] or maps_link(name=p["location_name"])
            lines.append(f"• {p['location_name']} ({p['category']}){mark}")
            lines.append(f"  🧭 {url}")
        await send_message(chat_id, "\n".join(lines))
    except Exception as e:
        await send_message(chat_id, t("search_failed", error=f"{type(e).__name__}: {e}"))


def nearest_places(places: list[dict], lat: float, lng: float) -> list[tuple[float, dict]]:
    """Unvisited places sorted by distance from the given location.
    Merged groups (group_id) are counted once. Returns [(distance_km, place), ...]."""
    groups: dict[str, list[dict]] = {}
    for p in places:
        key = p["group_id"] or f"solo-{p['row']}"
        groups.setdefault(key, []).append(p)

    result = []
    for group in groups.values():
        if any(p["visited"] for p in group):
            continue
        # Rows in a group may have different coordinates (e.g. merging two estimates) –
        # the representative is the entry closest to the user, not group[0]
        rep = min(group, key=lambda p: distance_km(lat, lng, p["lat"], p["lng"]))
        result.append((distance_km(lat, lng, rep["lat"], rep["lng"]), rep))
    result.sort(key=lambda x: x[0])
    return result


async def handle_location(chat_id: int, lat: float, lng: float) -> None:
    """Reply with a list of the closest saved (unvisited) places."""
    try:
        places = await asyncio.to_thread(read_rows)
        ranked = nearest_places(places, lat, lng)
        if not ranked:
            await send_message(chat_id, t("nearby_none_saved"))
            return

        nearby = [(d, p) for d, p in ranked if d <= NEARBY_RADIUS_KM][:NEARBY_LIMIT]
        if not nearby:
            d, p = ranked[0]
            url = p["maps_url"] or maps_link(name=p["location_name"])
            await send_message(chat_id, t("nearby_nothing", radius=NEARBY_RADIUS_KM,
                                          name=p["location_name"], dist=d, url=url))
            return

        lines = [t("nearby_header", count=len(nearby)), ""]
        for d, p in nearby:
            url = p["maps_url"] or maps_link(name=p["location_name"])
            dist = f"{d:.1f} km" if d < 10 else f"{d:.0f} km"
            lines.append(f"• {p['location_name']} – {dist} ({p['category']})")
            lines.append(f"  🧭 {url}")
        await send_message(chat_id, "\n".join(lines))
    except Exception as e:
        await send_message(chat_id, t("search_failed", error=f"{type(e).__name__}: {e}"))


async def run_dedup_check(chat_id: int) -> None:
    """Find suspected duplicates (Claude) and send suggestions with Merge/Keep buttons."""
    try:
        places = await asyncio.to_thread(read_rows)
        suggestions = await asyncio.to_thread(find_duplicates, places)

        if not suggestions:
            await send_message(chat_id, t("dedup_none"))
            return

        for s in suggestions:
            a, b = s["a"], s["b"]
            text = t("dedup_suggestion",
                     a_name=a["location_name"], a_date=a["date"],
                     b_name=b["location_name"], b_date=b["date"],
                     distance=s["distance_km"], reason=s["reason"])
            keyboard = {"inline_keyboard": [[
                {"text": t("btn_merge"), "callback_data": f"merge:{a['row']}:{b['row']}"},
                {"text": t("btn_keep"), "callback_data": "keep"},
            ]]}
            await send_message(chat_id, text, reply_markup=keyboard)

        await send_message(chat_id, t("dedup_done", count=len(suggestions)))
    except Exception as e:
        await send_message(chat_id, t("dedup_failed", error=f"{type(e).__name__}: {e}"))


async def handle_callback(callback: dict) -> None:
    """Handle a click on the Merge/Keep button."""
    callback_id = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data") or ""

    try:
        if data == "keep":
            await answer_callback(callback_id, t("cb_kept"))
            await send_message(chat_id, t("kept_msg"))
            return

        if data.startswith("merge:"):
            _, row_a, row_b = data.split(":")
            row_a, row_b = int(row_a), int(row_b)

            # Merging = the same group_id on both rows (keeps an existing group, otherwise a new one)
            places = await asyncio.to_thread(read_rows)
            by_row = {p["row"]: p for p in places}
            a, b = by_row.get(row_a), by_row.get(row_b)
            if not a or not b:
                await answer_callback(callback_id, t("cb_row_gone"))
                await send_message(chat_id, t("row_gone_msg", cmd=command_name("dedup")))
                return

            group = a["group_id"] or b["group_id"] or new_group_id()
            await asyncio.to_thread(set_group_ids, {row_a: group, row_b: group})
            await answer_callback(callback_id, t("cb_merged"))
            await send_message(chat_id, t("merged_msg", a=a["location_name"],
                                          b=b["location_name"]))
            return

        await answer_callback(callback_id)
    except Exception as e:
        await answer_callback(callback_id, t("cb_error"))
        await send_message(chat_id, t("merge_failed", error=f"{type(e).__name__}: {e}"))


@app.get("/", response_class=HTMLResponse)
async def root():
    return LANDING_HTML


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug")
async def debug(request: Request):
    check_map_token(request)
    return ffmpeg_diagnostics()


@app.get("/thumb/{row}.jpg")
async def thumb(row: int, request: Request):
    check_map_token(request, write=False)
    path = thumbnail_path(row)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="no thumbnail")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/data")
async def data(request: Request):
    check_map_token(request, write=False)
    try:
        places = await asyncio.to_thread(read_rows)
        # The header tells the map whether it may show the delete/visited buttons
        headers = {"X-Can-Edit": "1" if can_edit_map(request) else "0"}
        return JSONResponse(places, headers=headers)
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


def _export_places(places: list[dict]) -> list[dict]:
    """One place per group (group_id), the same as on the map.
    The visited state is aggregated across the whole group (consistently with the map)."""
    groups: dict[str, list[dict]] = {}
    for p in places:
        key = p["group_id"] or f"solo-{p['row']}"
        groups.setdefault(key, []).append(p)
    return [g[0] | {
        "urls": [x["url"] for x in g if x["url"]],
        "visited": any(x["visited"] for x in g),
    } for g in groups.values()]


def _build_export(places: list[dict], fmt: str) -> tuple[str, str, str]:
    """Return (content, media_type, extension) for geojson/gpx/kml."""
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
                   f'    <name>{escape(t("export_doc_name"))}</name>\n{marks}\n  </Document>\n</kml>\n')
        return content, "application/vnd.google-earth.kml+xml", "kml"

    raise HTTPException(status_code=400, detail="format must be geojson, gpx or kml")


@app.get("/export")
async def export(request: Request, format: str = "geojson"):
    """Export places for import into Mapy.cz, Organic Maps, Google My Maps..."""
    check_map_token(request, write=False)
    try:
        places = await asyncio.to_thread(read_rows)
        content, media_type, ext = _build_export(places, format.lower())
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)
    from fastapi.responses import Response
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{t("export_filename")}.{ext}"'})


@app.post("/visited")
async def visited(request: Request):
    """Mark places (rows) as visited/unvisited – called by the map."""
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
    """Delete a place (rows) from the sheet – called by the map after two-phase confirmation."""
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
    return HTMLResponse(render_map())


# Webhook registration (called automatically at startup, manually via --set-webhook)
async def set_webhook(public_url: str):
    params = {"url": f"{public_url}/webhook"}
    if WEBHOOK_SECRET:
        params["secret_token"] = WEBHOOK_SECRET
    result = await telegram_call("setWebhook", params)
    print(f"[webhook] setWebhook {public_url}/webhook -> {result}")


# Registering commands in the Telegram menu – the list shown after typing "/" in a chat
async def set_my_commands():
    result = await telegram_call("setMyCommands", {"commands": menu_commands()})
    print(f"[commands] setMyCommands -> {result}")


if __name__ == "__main__":
    if "--set-webhook" in sys.argv:
        idx = sys.argv.index("--set-webhook")
        public_url = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else input("Public URL: ")

        async def _cli_set_webhook():
            # runs outside the lifespan – the shared client must be closed manually
            try:
                await set_webhook(public_url)
            finally:
                await close_telegram_client()

        asyncio.run(_cli_set_webhook())
    else:
        import uvicorn
        # HOST=127.0.0.1 when deploying behind a reverse proxy (Caddy/nginx) – the app
        # is then not reachable directly from outside. Default 0.0.0.0 for Docker/containers.
        # "or" instead of a getenv default: an empty variable in .env (HOST=) must
        # behave as unset, otherwise int("") would crash the startup.
        uvicorn.run("main:app", host=os.getenv("HOST") or "0.0.0.0",
                    port=int(os.getenv("PORT") or 8000), reload=False)

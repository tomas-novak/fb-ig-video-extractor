import asyncio
import os
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
from geocoder import geocode, maps_link
from dedup import find_duplicates
from map_page import MAP_HTML

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
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
        task = asyncio.create_task(handle_callback(callback))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}

    message = update.get("message") or update.get("channel_post")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    # Příkaz: kontrola duplicitních míst
    if text.lower().startswith("/zkontroluj"):
        await send_message(chat_id, "🔍 Kontroluji duplicitní místa, chvíli počkej...")
        task = asyncio.create_task(run_dedup_check(chat_id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}

    if not is_valid_url(text):
        await send_message(chat_id, "Pošli mi URL Facebook nebo Instagram Reels videa.\n"
                                    "Nebo napiš /zkontroluj pro kontrolu duplicitních míst.")
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
async def debug():
    return ffmpeg_diagnostics()


@app.get("/data")
async def data():
    try:
        places = await asyncio.to_thread(read_rows)
        return JSONResponse(places)
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


@app.post("/visited")
async def visited(request: Request):
    """Označí místa (řádky) jako navštívená/nenavštívená – volá mapa."""
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


# Pomocný skript pro registraci webhooku
async def set_webhook(public_url: str):
    url = f"{TELEGRAM_API}/setWebhook"
    params = {"url": f"{public_url}/webhook"}
    if WEBHOOK_SECRET:
        params["secret_token"] = WEBHOOK_SECRET
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=params)
        print(r.json())


if __name__ == "__main__":
    if "--set-webhook" in sys.argv:
        idx = sys.argv.index("--set-webhook")
        public_url = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else input("Public URL: ")
        asyncio.run(set_webhook(public_url))
    else:
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)

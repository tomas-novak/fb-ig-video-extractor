import asyncio
import os
import sys
import tempfile
import httpx
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

load_dotenv()

from extractor import download_audio, extract_source, ffmpeg_diagnostics
from analyzer import analyze
from sheets import append_row, read_rows
from map_page import MAP_HTML

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


async def send_message(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
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
    return f"❌ Něco se nepovedlo: {err[:200]}"


@app.post("/webhook")
async def webhook(request: Request):
    # Volitelné ověření secret tokenu
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret")

    update = await request.json()

    message = update.get("message") or update.get("channel_post")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if not is_valid_url(text):
        await send_message(chat_id, "Pošli mi URL Facebook nebo Instagram Reels videa.")
        return {"ok": True}

    await send_message(chat_id, "⏳ Zpracovávám video, chvíli počkej...")

    # Zpracování v background tasku aby webhook rychle odpověděl
    asyncio.create_task(process_video(chat_id, text))

    return {"ok": True}


async def process_video(chat_id: int, url: str) -> None:
    audio_path = None
    try:
        # Stáhnutí audia
        audio_path, yt_info = await asyncio.to_thread(download_audio, url)

        # Analýza přes Gemini
        metadata = await asyncio.to_thread(analyze, audio_path, url, yt_info)

        # Uložení do Sheets
        await asyncio.to_thread(append_row, metadata)

        # Odpověď uživateli
        reply = (
            f"✅ Uloženo!\n"
            f"📍 {metadata.location_name}\n"
            f"🏷️ {metadata.category} | {metadata.tags}\n\n"
            f"{metadata.summary}"
        )
        await send_message(chat_id, reply)

    except Exception as e:
        await send_message(chat_id, friendly_error(str(e)))
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
            try:
                os.rmdir(os.path.dirname(audio_path))
            except OSError:
                pass


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug")
async def debug():
    return ffmpeg_diagnostics()


@app.get("/testdownload")
async def test_download(url: str, secret: str = "", full: int = 0):
    """Diagnostika: zkusí stáhnout (a volitelně analyzovat) přímo na serveru."""
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="bad secret")
    import traceback
    audio_path = None
    try:
        audio_path, info = await asyncio.to_thread(download_audio, url)
        result = {
            "ok": True,
            "step": "download",
            "size_bytes": os.path.getsize(audio_path),
            "title": (info.get("title") or "")[:120],
            "uploader": info.get("uploader") or info.get("channel"),
            "description": (info.get("description") or "")[:800],
        }
        if full:
            metadata = await asyncio.to_thread(analyze, audio_path, url, info)
            result["step"] = "analyze"
            result["location_name"] = metadata.location_name
            result["category"] = metadata.category
            result["tags"] = metadata.tags
            result["transcript"] = metadata.transcript[:800]
        return result
    except Exception as e:
        return JSONResponse({
            "ok": False,
            "error_type": type(e).__name__,
            "error": str(e)[:1500],
            "traceback": traceback.format_exc()[-1500:],
        }, status_code=500)
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                os.rmdir(os.path.dirname(audio_path))
            except OSError:
                pass


@app.get("/data")
async def data():
    try:
        places = await asyncio.to_thread(read_rows)
        return JSONResponse(places)
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

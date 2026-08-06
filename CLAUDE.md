# CLAUDE.md — FB/IG Video Extractor

## What this project does

A Telegram bot that takes a Facebook Reels or Instagram Reels URL, automatically
pulls the video content, transcribes the audio, extracts the place and saves the
metadata to Google Sheets.

## Architecture

```
User (phone)
  → sends a URL to the Telegram bot
      → Python API (VPS)
          → yt-dlp downloads the VIDEO (not audio – FB offers no audio-only stream to datacenters)
          → Gemini Flash analyzes the video: audio transcript + on-screen text + caption (one call)
          → Google Sheets API saves a row
          → Telegram Bot API replies to the user
```

Note: we send Gemini the whole video (not extracted audio). The reason: on a
datacenter IP Facebook does not offer a separate audio stream, only video. On top
of that Gemini reads the text shown in the video, which makes the place
determination more accurate.

## Stack

- **Runtime**: Python 3.10+ (verified on 3.10.12 on the production VPS; no construct in the code requires 3.11)
- **Web framework**: FastAPI + uvicorn
- **Telegram**: python-telegram-bot or direct Bot API calls
- **Video download**: yt-dlp (format `hd/sd/best`)
- **AI (video analysis)**: Google Gemini 2.5 Flash (multimodal video – audio + image)
- **Database**: Google Sheets (google-auth + gspread)
- **Hosting**: own VPS (Ubuntu 22.04, systemd + Caddy)

## Key files

```
FB_IG_video_extractor/
├── CLAUDE.md          # this file
├── README.md          # user documentation (English, default)
├── README.cs.md       # user documentation (Czech)
├── main.py            # FastAPI app + Telegram webhook handler
├── extractor.py       # yt-dlp download logic
├── analyzer.py        # Gemini API calls (transcription + analysis)
├── i18n.py            # bot language (BOT_LANGUAGE) + categories (CATEGORIES) + texts
├── sheets.py          # Google Sheets writing
├── models.py          # data models (VideoMetadata)
├── requirements.txt
├── deploy/            # systemd unit, Caddyfile, update and DuckDNS scripts
├── docs/deploy-vps.md # general guide for deploying to your own VPS (English)
└── .env.example       # environment variables template
```

## Environment variables

```
TELEGRAM_BOT_TOKEN=       # token from @BotFather
GEMINI_API_KEY=           # Google AI Studio
GOOGLE_SHEETS_ID=         # Google Sheet ID
GOOGLE_SERVICE_ACCOUNT=   # service account JSON (base64 or path)
WEBHOOK_SECRET=           # optional secret for verifying Telegram webhooks
BOT_LANGUAGE=             # language of bot replies, the map and AI summaries: en (default) / cs
CATEGORIES=               # custom comma-separated categories; the last one is the fallback
PUBLIC_URL=               # public address of the instance (webhook registration at startup)
HOST=                     # listen address; behind a reverse proxy 127.0.0.1 (default 0.0.0.0)
```

## Google Sheets structure (Sheet1)

| A: Date | B: URL | C: Author | D: Title | E: Place | F: Lat | G: Lng | H: Category | I: Tags | J: Summary | K: Transcript | L: Source | M: group_id |

**M: group_id** — places with the same group_id are shown on the map as a single
pin with multiple videos. Merging is proposed by Claude Haiku (the dedup command
in Telegram → Merge/Keep buttons). See `dedup.py`. Merging deletes nothing and is
reversible (clear the group_id in the sheet).

## Supported URL formats

- `https://www.facebook.com/reel/ID`
- `https://www.instagram.com/reel/ID`
- `https://www.instagram.com/p/ID`
- `https://www.tiktok.com/@user/video/ID`
- `https://www.youtube.com/shorts/ID`
- Share links (shortened: `fb.watch`, `vm.tiktok.com`, `youtu.be`) — yt-dlp expands them automatically

## Categories (for filtering on the map)

Default (en): `swimming` · `hiking` · `food` · `culture` · `nature` · `sport` · `fun` · `hotel` · `other`

Default (cs): `koupání` · `turistika` · `jídlo` · `kultura` · `příroda` · `sport` · `zábava` · `hotel` · `jiné`

Categories are configurable through the `CATEGORIES` env variable (see `i18n.py`);
the last one in the list is the fallback. The language of the bot's replies, the
map and Gemini summaries is driven by `BOT_LANGUAGE` (`en` default / `cs`); the
audio transcript stays in the language of the video.

## Development

```bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env        # fill in the values
uvicorn main:app --reload --port 8000
```

## Language policy

The repository is public and English is its working language.

- Write commit messages, branch names and PR text in **English**.
- Code comments, docstrings and development documentation (this file) are in **English**.
- Czech stays only where it is product data, not prose:
  - `README.cs.md` (Czech user documentation)
  - the `cs` message catalog, command names and categories in `i18n.py`
  - the `cs` Gemini prompt templates in `analyzer.py`
  - the `T_cs` map UI dictionary in `map_page.py`
  - test fixtures and assertions, since `tests/conftest.py` pins `BOT_LANGUAGE=cs`
    to exercise the Czech path

## Deployment (VPS)

A general step-by-step guide (for anyone, not just our server): `docs/deploy-vps.md`.

1. The application lives in `/opt/fbig-bot`, Python venv, runs as a systemd
   service (`deploy/fbig-bot.service`) under the `fbigbot` user
2. Caddy as a reverse proxy (`deploy/Caddyfile`) — HTTPS from Let's Encrypt
   automatically, domain via DuckDNS
3. `HOST=127.0.0.1` in `.env` — only Caddy is exposed
4. The webhook registers itself at startup based on `PUBLIC_URL`
   (manual variant: `python main.py --set-webhook <url>`)
5. Updates: `deploy/update.sh` (git pull + dependencies + yt-dlp + restart)

The unit sets `MemoryMax`, `OOMScoreAdjust=1000` and a lower CPU/IO weight so
that under memory pressure the system always kills the bot and not the other
services on the server.

The Docker variant (`Dockerfile`, `docker-compose.yml`) remains as an alternative.

## Migration history

The project originally ran on Railway. Since 2026-08-06 it runs on its own VPS
(see "Deployment (VPS)" above); the setup is proven, and `railway.toml`,
`nixpacks.toml` and `gen_railway_env.py` were deleted. The deployment procedure
is now generalized in `docs/deploy-vps.md` rather than tied to the specific
history of a single move.

## Future extensions

- Google My Maps integration (showing pins from Sheets)
- Filtering the map by category
- Migrating the database to Supabase + the map to Vercel — a finished design
  exists, the owner keeps it outside the repo

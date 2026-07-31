# FB/IG Video Extractor — Travel Journal via Telegram

[![CI](https://github.com/tomas-novak/fb-ig-video-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/tomas-novak/fb-ig-video-extractor/actions/workflows/ci.yml)

🇨🇿 **Česká verze: [README.cs.md](README.cs.md)**

Send a short-video URL (Facebook/Instagram Reels, TikTok, YouTube Shorts) to
**your own** Telegram bot → AI automatically extracts the place, transcribes
the audio and saves everything to Google Sheets. You then see your saved
places on an interactive map with filters.

This is a **self-hosted** tool: everyone deploys their own instance with
their own bot, their own spreadsheet and their own API keys. There is no
shared public bot.

## Motivation

While scrolling social media I keep running into interesting places in videos
(swimming spots, trips, restaurants...). I want to save them easily from my
phone without filling anything in by hand.

## How it works

1. You find an interesting video on Facebook, Instagram, TikTok or YouTube
2. You tap "Share" → copy the URL → send it to your bot on Telegram
   (shortened share links work too: `fb.watch`, `vm.tiktok.com`, `youtu.be`)
3. The bot replies within ~30 seconds:
   ```
   ✅ Saved!
   📍 Slaný Swimming Pool
   🏷️ swimming | outdoor, kids, pool

   A modern water park in Slaný with pools for kids and adults.
   Fun for the whole family.
   🧭 https://www.google.com/maps/search/?api=1&query=50.23,14.09&query_place_id=...
   ```
4. The place is saved to Google Sheets including precise GPS coordinates
   (Google Places), an audio transcript and a Google Maps link
5. On `/map` you see all places on a map — filtering by categories and tags,
   marking visited places, merging duplicates

## Tech stack

- Telegram Bot API (input interface from your phone)
- yt-dlp (video download)
- Google Gemini Flash (video analysis: transcript + place + category)
- Google Places API (precise coordinates + map links)
- Claude Haiku (judging duplicate places)
- Google Sheets (place database)
- FastAPI (backend, self-hosted on a VPS)
- Leaflet + OpenStreetMap (map)

## Setup — your own instance (~15 minutes, all free)

You need 4 keys and one deployment. Step by step:

### 1. Telegram bot (2 min)
On Telegram, message [@BotFather](https://t.me/BotFather) → `/newbot` →
pick a name. You get a **token** (`123456:ABC-...`) → `TELEGRAM_BOT_TOKEN`.

### 2. Gemini API key (2 min)
[aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) →
Create API key → `GEMINI_API_KEY`. The free tier is more than enough.

### 3. Google Sheets + service account (5–10 min, the hardest step)
1. Create an empty Google spreadsheet; copy its ID from the URL →
   `GOOGLE_SHEETS_ID`
2. [console.cloud.google.com](https://console.cloud.google.com) → create a
   project → enable the **Google Sheets API**
3. Credentials → Create Credentials → **Service Account** → under it Keys →
   Add Key → JSON (a file downloads)
4. The JSON file's content (one line) → `GOOGLE_SERVICE_ACCOUNT_JSON`
5. **Share** the spreadsheet (Editor) with the service account's e-mail
   (`...@....iam.gserviceaccount.com`)

### 4. Optional keys and settings
- `GOOGLE_MAPS_API_KEY` — precise place coordinates (Places API New;
  without it, AI estimates are used)
- `ANTHROPIC_API_KEY` — duplicate-place check via the `/dedup` command
- `MAP_TOKEN` — map protection (without it the map is public)
- `WEBHOOK_SECRET` — Telegram webhook verification
- `BOT_LANGUAGE` — language of bot replies, the map and AI summaries:
  `en` (default) or `cs`. The audio transcript always stays in the
  video's original language.
- `CATEGORIES` — custom comma-separated categories. The default set follows
  `BOT_LANGUAGE`: for `en` it's
  `swimming,hiking,food,culture,nature,sport,fun,hotel,other`, for `cs`
  the Czech equivalents — so switching the language also switches the
  default categories. The last category in the list is the catch-all —
  used when the AI can't decide.

### 5. Deployment

The bot needs to run as a long-lived service — processing one video takes
tens of seconds up to a few minutes, so request-scoped serverless functions
(Vercel and friends) won't work.

**VPS (recommended):** a full step-by-step guide, including free HTTPS, is in
[docs/migration/01-phase-a-vps.md](docs/migration/01-phase-a-vps.md) (written
in Czech). In short: a Python venv plus the systemd unit from
`deploy/fbig-bot.service`, with Caddy as the reverse proxy.

**Docker (VPS, NAS, Raspberry Pi):**
```bash
cp .env.example .env   # fill in the keys + PUBLIC_URL
docker compose up -d
```

### 6. After deployment
1. Send `/id` to the bot → it returns your Telegram ID
2. Set `TELEGRAM_ALLOWED_USERS=<your_id>` — otherwise anyone can use the
   bot and burn your API credit
3. Map: `https://your-instance/map?token=MAP_TOKEN`

Detailed technical docs: [CLAUDE.md](CLAUDE.md) · feature plan:
[ROADMAP.md](ROADMAP.md) · changes: [CHANGELOG.md](CHANGELOG.md)

## Bot commands

- send a video URL → saves the place
- send your location (Telegram Location attachment) → closest saved places
- `/search <text>` (alias `/hledej`) — search your saved places
- `/dedup` (alias `/zkontroluj`) — check for duplicate places
- `/id` — your Telegram user ID (for setting up the whitelist)
- `/help` (aliases `/start`, `/napoveda`) — list all commands

Commands are also registered in the Telegram command menu (shown after
typing `/` in the chat), in the language set by `BOT_LANGUAGE`.

## Development and tests

```bash
pip install -r requirements-dev.txt
pytest          # tests (run without real API keys)
ruff check .    # lint
```

Both are checked automatically by GitHub Actions on every push and pull
request.

## Known limitations

- **Instagram requires cookies.** From datacenter IPs (any VPS or PaaS)
  Instagram usually blocks anonymous downloads ("login required"). Solution:
  export cookies of a logged-in account (an extension like *Get cookies.txt*)
  and set `INSTAGRAM_COOKIES` (file content) or `COOKIES_FILE` (file path).
  Cookies expire from time to time and need refreshing.
- **Facebook occasionally blocks datacenter IPs.** It usually works
  anonymously, but when blocked, the same cookie approach helps. Check your
  instance's state at the `/debug?token=MAP_TOKEN` endpoint.
- **YouTube often requires cookies on servers.** YouTube commonly blocks
  datacenter IPs with "Sign in to confirm you're not a bot". The solution is
  the same as for Instagram — add cookies of a logged-in YouTube/Google
  account to the cookies file (one `cookies.txt` can contain both domains;
  the variable is called `INSTAGRAM_COOKIES` for historical reasons, its
  content applies to all domains in the file).
- **TikTok not yet verified in production.** yt-dlp supports TikTok
  (including `vm.tiktok.com` share links) and downloads anonymously;
  reliability from datacenter IPs may vary with TikTok's anti-bot measures.
  If downloads keep failing, open an issue with the error message from the
  bot's reply.
- **The Gemini free tier has rate limits.** When sending several videos in
  quick succession, analysis may fail temporarily — wait a moment and send
  the video again.
- **Video length.** The bot is built for short videos (Reels, TikTok,
  Shorts). Videos longer than 10 minutes are rejected before downloading —
  the limit can be changed via `MAX_VIDEO_MINUTES` (0 = no limit). Even for
  allowed longer videos, Gemini processing may time out (max. 2 minutes).
- **Coordinates without `GOOGLE_MAPS_API_KEY` are only estimates.** Gemini
  estimates coordinates and can be off by kilometers; with a Places API key
  the place is looked up precisely.
- **Changing `BOT_LANGUAGE` / `CATEGORIES` does not change old data.**
  Previously saved rows keep their original language and categories; on the
  map, categories outside the current configuration are shown in grey.

## Legal notice

This tool downloads videos from Facebook and Instagram using
[yt-dlp](https://github.com/yt-dlp/yt-dlp), which may violate Meta's terms
of service. The tool is intended solely for **personal archiving** of
content for your own use (saving trip tips). You use it at your own risk.
Do not download or distribute other people's content in ways that violate
its creators' copyright.

## License

The code is available under the [MIT](LICENSE) license.

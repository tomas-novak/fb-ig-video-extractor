# Roadmap — the path to a successful open-source project

A plan of changes and new features ordered by impact. The goal: for people on
GitHub to notice the project, be able to get it running, and have a reason to use it.

---

## Phase 0 — Readiness for going public

The necessary groundwork before it makes sense to promote the repo.

- [x] **Add `LICENSE` (MIT)** — the standard MIT text with a copyright line
  (name + year). GitHub detects the license automatically and shows it in the
  repo header.
- [x] **A `## License` section in the README** — one sentence linking to LICENSE.
- [x] **A legal disclaimer in the README** — downloading videos via yt-dlp
  violates Meta's terms of service. State it clearly: the tool is for personal
  archiving, use at your own risk.
- [x] **Clarify the self-hosted nature** — the README used to invite readers to
  use a private bot. Rephrase it to "your own bot" (everyone deploys their own
  instance with their own Sheet and their own keys). Consider a whitelist of
  allowed Telegram user IDs in the code so strangers do not burn Gemini credit.
  *(done: `TELEGRAM_ALLOWED_USERS` + the `/id` command, fail-closed validation)*
- [x] **Fix the placeholder in `.env.example`** — `AIzaSy_your_gemini_api_key_here`
  starts with the real prefix of Google keys and secret scanners flag it as a
  false positive. Rewrite it to a neutral `your_gemini_api_key_here`.
- [x] **BLOCKER: protect the map's mutating endpoints** — `POST /delete` and
  `POST /visited` had no authentication; anyone who found the instance URL could
  delete data. On top of that `GET /data` publicly served the whole place database.
  *(done: the `MAP_TOKEN` env variable; the map is opened via `/map?token=...` and
  passes the token to `/data`, `/visited` and `/delete`; the server verifies it with
  a constant-time comparison. An empty `MAP_TOKEN` = a public map — a deliberate
  choice by the self-hoster.)*

---

## Phase 1 — A demo that sells

The highest impact-to-effort ratio. People decide about a star within a few
seconds of scrolling — they need to see, not to read.

- [ ] **A GIF of the main flow in the README** — a phone screen: pasting a reel
  URL into Telegram → the bot's reply with the place, category and summary. Record
  the screen, convert it to a GIF (e.g. via ffmpeg), and put it right below the
  README heading.
- [ ] **A screenshot of the map** — the map with pins, category filters enabled and
  a place popup open. It shows "what's in it for me" — the target state after a few
  weeks of use.
- [ ] **A sample output in Google Sheets** — a screenshot of the sheet with a few
  rows (anonymized / sample data).
- [x] **A public demo map (optional)** — a `/map` instance filled with sample data,
  linked from the README. A visitor gets a feel for the product without installing.
  *(done: a static `docs/index.html` with 5 sample places, deployed via GitHub
  Pages at https://tomas-novak.github.io/fb-ig-video-extractor/ — not the real
  `/map`, since that needs a live bot; category/tag filtering and the visited
  toggle work the same, no backend required)*

---

## Phase 2 — Cut setup from an hour to minutes

Every manual step filters out a portion of the interested people. Right now 4
credentials and a manual webhook registration are needed.

- [x] **Automatic webhook registration at startup** — instead of a manual
  `python main.py --set-webhook`, call `setWebhook` in the `lifespan` handler when
  the `PUBLIC_URL` env variable is set. One setup step disappears.
  *(done: on Railway it works fully automatically via `RAILWAY_PUBLIC_DOMAIN`,
  elsewhere via `PUBLIC_URL`; a failed registration does not prevent startup)*
- [x] **`Dockerfile` + `docker-compose.yml`** — for self-hosters (VPS, NAS,
  Raspberry Pi). The compose file loads `.env`, a single command: `docker compose up`.
- [ ] **A "Deploy on Railway" button** — a Railway template with predefined env
  variables (names + descriptions). The user only fills in the values in a form.
  *(requires publishing a template from the author's Railway account — only after
  the repo is public)*
- [x] **A setup guide in the README** — a numbered procedure with all the steps:
  1. BotFather → token (2 min)
  2. Google AI Studio → Gemini key (2 min)
  3. Google Cloud → service account + sharing the Sheet (5–10 min, the hardest
     step — add screenshots)
  4. Deploy (Railway button or Docker)

  State an estimate of the total time ("~15 minutes, all free") — it lowers the barrier.
- [ ] **An optional SQLite backend (a bolder step)** — the service account for
  Sheets is the most annoying credential. Abstract `sheets.py` into a simple storage
  interface (append a row, read all, update a cell) and add a SQLite implementation.
  With SQLite only 2 keys are needed (Telegram + Gemini) and the setup is trivial.
  Sheets remains the default option for non-programmers.

---

## Phase 3 — English and configurability

The Czech GitHub market is small. Opening up to the world = many times the reach.

- [x] **English README as the default** — `README.md` in English, the Czech version
  next to it as `README.cs.md` (cross-links in the header).
- [x] **The bot's reply language as configuration** — the `BOT_LANGUAGE` env
  variable (e.g. `cs` / `en`). Extract the message texts from `main.py` into a
  dictionary, and pass the Gemini prompt in `analyzer.py` an instruction about which
  language to write the summary and transcript in.
  *(done: `i18n.py` – a cs/en text catalog, bilingual Gemini prompts, a translated
  map and duplicate reasoning; the transcript stays in the language of the video.
  The English command aliases `/search` and `/dedup` always work.)*
- [x] **Categories as configuration** — the categories (`koupání`, `turistika`, …)
  were hardcoded in the prompt and the map. Extract them into an env variable
  (`CATEGORIES=swimming,hiking,food,...`) or a config file; both the prompt and the
  map filters read them from there.
  *(done: `CATEGORIES` in `i18n.py`, a default set per language; the last category
  is the fallback. The map assigns colors by the order in the configuration, and
  categories outside the configuration – older data – are shown in grey.)*

---

## Phase 4 — TikTok and YouTube Shorts

The "places from short videos" use case lives mostly on TikTok. yt-dlp already
handles both platforms — it is mostly about allowing the URL formats.

- [x] **TikTok** — add recognition of `tiktok.com` URLs (including short
  `vm.tiktok.com` share links) to the validation in `main.py` / `extractor.py`.
  Test whether yt-dlp downloads reliably from a datacenter IP; document any limits.
  *(done in the code; reliability from a datacenter IP remains to be verified in
  practice — a note in the README / Known limitations)*
- [x] **YouTube Shorts** — allow `youtube.com/shorts/ID` URLs. Watch out for
  YouTube's anti-bot measures on datacenter IPs — document a possible need for cookies.
  *(done: cookies are sent for YouTube the same way as for Instagram, the anti-bot
  blocking has its own clear message from the bot + a description in the README)*
- [x] **Extend the `L: Source` column** with the new values (tiktok, youtube) so
  that filters work.
  *(done: `extract_source()` is the single place determining the source — the
  analyzer now uses it instead of its own FB/IG condition)*

---

## Phase 5 — From an archive to a product for the road

Features that turn a passive collection of places into a tool used on the trip itself.

- [x] **"Nearby places"** — the user sends the bot a location (Telegram Location
  attachment) → the bot returns saved places within X km, sorted by distance, with a
  navigation link. The coordinates are already in the sheet, and the distance
  calculation (haversine) is a few lines. A killer feature: you use it when you
  actually are somewhere.
  *(done: the 5 closest unvisited places within 50 km, merged groups counted once;
  when there is nothing in range it shows at least the closest place)*
- [x] **Sharing the map** — a read-only link to `/map` for a partner/friends while
  planning. Consider a simple token in the URL so the map is not completely public
  (it also hides the delete/visited buttons from outside visitors).
  *(done: `MAP_VIEW_TOKEN` – the server rejects mutations, the map hides the buttons
  based on the X-Can-Edit header)*
- [x] **Data export** — an `/export` endpoint with GeoJSON, GPX and KML formats.
  It allows importing pins into Mapy.cz, Organic Maps or Google My Maps. It signals
  "your data is yours" — the travel community appreciates that.
  *(done: `/export?format=geojson|gpx|kml`, links directly in the map panel; one
  place per group, including all video URLs)*
- [x] **Search in Telegram (optional)** — a search command scans place names, tags
  and summaries and returns the few best matches with links.
  *(done: diacritics-insensitive – "hriste" finds "hřiště"; visited ones marked ✅)*

---

## Phase 6 — Credibility

It will not bring new users, but it raises the conversion of those who already came.

- [x] **Basic tests** — at least for the pure functions: URL validation, parsing the
  Gemini response, the dedup logic. `pytest`, without needing real API keys (mock).
  *(done: 108 tests in `tests/` — URLs/commands/whitelist, parsing Gemini and Claude
  responses, the dedup prefilter, search, nearby places, GeoJSON/GPX/KML export,
  sheet row parsing; `pip install -r requirements-dev.txt && pytest`)*
- [x] **GitHub Actions CI** — run the tests + `ruff` lint on every push, a badge in
  the README.
  *(done: `.github/workflows/ci.yml`, ruff configuration in `pyproject.toml`)*
- [x] **A "Known limitations" section in the README** — FB sometimes blocks
  datacenter IPs; describe the workaround via cookies (`--cookies` in yt-dlp), the
  rate limits of the Gemini free tier, and the maximum video length.
- [x] **CHANGELOG.md** — keep a brief log of changes from the first public release.
  *(created; until the first release changes are tracked under "Unreleased")*

---

## Recommended order for the first week

1. All of Phase 0 (a few hours, unblocks going public)
2. Phase 1: GIF + screenshots (the highest impact on stars)
3. Phase 2: Docker + auto-webhook
4. Phase 3: English README

"Nearby places" from Phase 5 is worth doing right away regardless of GitHub — it is
useful for your own use. Add the rest of Phase 5 and the SQLite backend only
according to real user interest.

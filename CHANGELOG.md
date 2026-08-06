# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The project has no numbered releases yet — changes are tracked under "Unreleased"
and will be rolled into a version at the first public release.

## Unreleased

### Added
- The `/help` command (aliases `/start`, `/napoveda`) — lists all the bot's
  commands and what they do. The commands are also registered into the Telegram
  menu at startup (`setMyCommands`), so they are offered after typing `/` in a chat.
- Bot language as configuration: `BOT_LANGUAGE` (`en` default / `cs`) drives the
  bot's replies, the map texts, the language of Gemini summaries/tags and of the
  duplicate reasoning (`i18n.py`). The audio transcript stays in the original
  language of the video. The English command aliases `/search` and `/dedup` work
  regardless of the language.
- Categories as configuration: `CATEGORIES` (comma-separated list, default set
  per language). The last category is the fallback; the map assigns colors by the
  order in the configuration and shows unknown categories in grey.
- English README as the default (`README.md`), Czech version in `README.cs.md`.
- Support for TikTok (including `vm.tiktok.com` share links) and YouTube Shorts
  (including `youtu.be`). The Source column now also takes the values `tiktok` and
  `youtube`; cookies are used for YouTube the same way as for Instagram, and
  YouTube's anti-bot blocking has its own clear message from the bot.
- Video length limit `MAX_VIDEO_MINUTES` (default 10, 0 = off) — a long video sent
  by mistake (e.g. `youtube.com/watch`) is rejected by the bot before downloading
  instead of an expensive analysis in Gemini.
- Basic tests (`pytest`) for the pure functions: URL and command validation,
  parsing Gemini/Claude responses, the dedup prefilter, search, "nearby places",
  GeoJSON/GPX/KML export, sheet row parsing.
- GitHub Actions CI: `ruff` lint + tests on every push and pull request, badge in
  the README.
- A "Known limitations" section in the README (cookies for Instagram, datacenter
  IP blocking, Gemini rate limits, video length, coordinate accuracy).
- This CHANGELOG.

### Existing features (state before the changelog was introduced)
- Telegram bot: saving a place from a Facebook/Instagram video URL (yt-dlp +
  Gemini 2.5 Flash + Google Sheets), duplicate detection by URL and video ID.
- User whitelist (`TELEGRAM_ALLOWED_USERS`), the `/id` command.
- Geocoding via the Google Places API (exact coordinates + a maps link).
- Interactive map (`/map`) with filters, deletion and marking places as visited;
  token protection (`MAP_TOKEN`), read-only sharing (`MAP_VIEW_TOKEN`).
- Duplicate place check (Claude Haiku) with Merge/Keep buttons.
- "Nearby places": the bot replies to a shared location with the closest saved places.
- Full-text search (diacritics-insensitive).
- Export via `/export` in GeoJSON, GPX and KML formats.
- Automatic Telegram webhook registration at startup, Docker/Compose deployment,
  a setup guide in the README.

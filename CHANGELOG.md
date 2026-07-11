# Changelog

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/).
Projekt zatím nemá číslované release — změny se evidují pod „Nevydáno"
a při prvním veřejném release se překlopí do verze.

## Nevydáno

### Přidáno
- Podpora TikTok (včetně `vm.tiktok.com` share linků) a YouTube Shorts
  (včetně `youtu.be`). Sloupec Zdroj nově nabývá hodnot `tiktok` a
  `youtube`; cookies se pro YouTube používají stejně jako pro Instagram
  a anti-bot blokace YouTube má vlastní srozumitelnou hlášku bota.
- Základní testy (`pytest`) pro čisté funkce: validace URL a příkazů,
  parsování Gemini/Claude odpovědí, dedup předfiltr, vyhledávání `/hledej`,
  „místa poblíž", export GeoJSON/GPX/KML, parsování řádků tabulky.
- GitHub Actions CI: `ruff` lint + testy na každý push a pull request,
  badge v README.
- Sekce „Známé limity" v README (cookies pro Instagram, blokace datacenter
  IP, rate limity Gemini, délka videa, přesnost souřadnic).
- Tento CHANGELOG.

### Stávající funkce (stav před zavedením changelogu)
- Telegram bot: uložení místa z URL Facebook/Instagram videa (yt-dlp +
  Gemini 2.5 Flash + Google Sheets), detekce duplicit podle URL i video ID.
- Whitelist uživatelů (`TELEGRAM_ALLOWED_USERS`), příkaz `/id`.
- Geokódování přes Google Places API (přesné souřadnice + odkaz na mapy).
- Interaktivní mapa (`/map`) s filtry, mazáním a označováním navštívených
  míst; ochrana tokenem (`MAP_TOKEN`), read-only sdílení (`MAP_VIEW_TOKEN`).
- Kontrola duplicitních míst `/zkontroluj` (Claude Haiku) s tlačítky
  Sloučit/Ponechat.
- „Místa poblíž": bot odpoví na poslanou polohu nejbližšími uloženými místy.
- Fulltextové hledání `/hledej` (bez diakritiky).
- Export `/export` ve formátech GeoJSON, GPX a KML.
- Automatická registrace Telegram webhooku při startu, Docker/Compose
  nasazení, setup průvodce v README.

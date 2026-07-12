# Changelog

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/).
Projekt zatím nemá číslované release — změny se evidují pod „Nevydáno"
a při prvním veřejném release se překlopí do verze.

## Nevydáno

### Přidáno
- Příkaz `/help` (aliasy `/start`, `/napoveda`) — vypíše všechny příkazy
  bota a co dělají. Příkazy se navíc při startu registrují do menu
  Telegramu (`setMyCommands`), takže se nabízejí po napsání `/` v chatu.
- Jazyk bota do konfigurace: `BOT_LANGUAGE` (`en` výchozí / `cs`) řídí odpovědi bota,
  texty mapy, jazyk Gemini shrnutí/tagů i zdůvodnění duplicit (`i18n.py`).
  Přepis zvuku zůstává v původním jazyce videa. Anglické aliasy příkazů
  `/search` a `/dedup` fungují nezávisle na jazyce.
- Kategorie do konfigurace: `CATEGORIES` (čárkou oddělený seznam, výchozí
  sada podle jazyka). Poslední kategorie je záchytná; mapa přiděluje barvy
  podle pořadí v konfiguraci a neznámé kategorie zobrazí šedě.
- Anglické README jako výchozí (`README.md`), česká verze v `README.cs.md`.
- Podpora TikTok (včetně `vm.tiktok.com` share linků) a YouTube Shorts
  (včetně `youtu.be`). Sloupec Zdroj nově nabývá hodnot `tiktok` a
  `youtube`; cookies se pro YouTube používají stejně jako pro Instagram
  a anti-bot blokace YouTube má vlastní srozumitelnou hlášku bota.
- Limit délky videa `MAX_VIDEO_MINUTES` (výchozí 10, 0 = vypnuto) —
  omylem poslané dlouhé video (např. `youtube.com/watch`) bot odmítne
  ještě před stažením místo drahé analýzy v Gemini.
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

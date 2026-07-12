# FB/IG Video Extractor — Cestovní deník přes Telegram

[![CI](https://github.com/tomas-novak/fb-ig-video-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/tomas-novak/fb-ig-video-extractor/actions/workflows/ci.yml)

🇬🇧 **English version: [README.md](README.md)**

Pošli URL krátkého videa (Facebook/Instagram Reels, TikTok, YouTube Shorts)
**svému** Telegram botovi → AI automaticky vytáhne místo, přepíše zvuk a uloží
vše do Google Sheets. Uložená místa pak vidíš na interaktivní mapě s filtry.

Jde o **self-hosted** nástroj: každý si nasazuje vlastní instanci s vlastním
botem, vlastní tabulkou a vlastními API klíči. Neexistuje žádný sdílený
veřejný bot.

## Motivace

Při scrollování sociálních sítí narážím na zajímavá místa ve videích (koupaliště,
výlety, restaurace...). Chci je jednoduše uložit z telefonu bez ručního vyplňování.

## Jak to funguje

1. Najdeš zajímavé video na Facebooku, Instagramu, TikToku nebo YouTube
2. Klikneš "Sdílet" → zkopíruješ URL → pošleš svému botovi v Telegramu
   (fungují i zkrácené share linky: `fb.watch`, `vm.tiktok.com`, `youtu.be`)
3. Bot do ~30 sekund odpoví:
   ```
   ✅ Uloženo!
   📍 Koupaliště Slaný
   🏷️ koupání | outdoor, s dětmi, bazén

   Moderní aquapark v Slaném s bazény pro děti i dospělé.
   Zábava pro celou rodinu.
   🧭 https://www.google.com/maps/search/?api=1&query=50.23,14.09&query_place_id=...
   ```
4. Místo se uloží do Google Sheets včetně přesných GPS souřadnic (Google
   Places), přepisu zvuku a odkazu na Google Maps
5. Na `/map` vidíš všechna místa na mapě — filtrování podle kategorií a tagů,
   označování navštívených míst, slučování duplicit

## Technologie

- Telegram Bot API (vstupní rozhraní z mobilu)
- yt-dlp (stažení videa)
- Google Gemini Flash (analýza videa: přepis + místo + kategorie)
- Google Places API (přesné souřadnice + odkazy na mapy)
- Claude Haiku (posuzování duplicitních míst)
- Google Sheets (databáze míst)
- FastAPI + Railway (backend hosting)
- Leaflet + OpenStreetMap (mapa)

## Nastavení — vlastní instance (~15 minut, vše zdarma)

Potřebuješ 4 klíče a jedno nasazení. Postupně:

### 1. Telegram bot (2 min)
V Telegramu napiš [@BotFather](https://t.me/BotFather) → `/newbot` → zvol
jméno. Dostaneš **token** (`123456:ABC-...`) → `TELEGRAM_BOT_TOKEN`.

### 2. Gemini API klíč (2 min)
[aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) →
Create API key → `GEMINI_API_KEY`. Free tier bohatě stačí.

### 3. Google Sheets + service account (5–10 min, nejtěžší krok)
1. Vytvoř prázdnou Google tabulku; z URL zkopíruj její ID → `GOOGLE_SHEETS_ID`
2. [console.cloud.google.com](https://console.cloud.google.com) → vytvoř
   projekt → zapni **Google Sheets API**
3. Credentials → Create Credentials → **Service Account** → u něj Keys →
   Add Key → JSON (stáhne se soubor)
4. Obsah JSON souboru (jeden řádek) → `GOOGLE_SERVICE_ACCOUNT_JSON`
5. Tabulku **nasdílej** (Editor) na e-mail service accountu
   (`...@....iam.gserviceaccount.com`)

### 4. Volitelné klíče a nastavení
- `GOOGLE_MAPS_API_KEY` — přesné souřadnice míst (Places API New; bez něj se
  použijí odhady AI)
- `ANTHROPIC_API_KEY` — kontrola duplicitních míst příkazem `/zkontroluj`
- `MAP_TOKEN` — ochrana mapy (bez něj je mapa veřejná)
- `WEBHOOK_SECRET` — ověřování Telegram webhooků
- `BOT_LANGUAGE` — jazyk odpovědí bota, mapy a AI shrnutí: `en` (výchozí)
  nebo `cs`. **Pro češtinu je potřeba nastavit `BOT_LANGUAGE=cs`.**
  Přepis zvuku zůstává vždy v původním jazyce videa.
- `CATEGORIES` — vlastní kategorie oddělené čárkou. Výchozí sada se řídí
  podle `BOT_LANGUAGE`: pro `cs` je to
  `koupání,turistika,jídlo,kultura,příroda,sport,zábava,hotel,jiné`, pro
  `en` anglické ekvivalenty — přepnutím jazyka se tedy mění i výchozí
  kategorie. Poslední kategorie v seznamu je záchytná — použije se, když
  AI žádnou neurčí.

### 5. Nasazení

**Railway:** nové Project → Deploy from GitHub repo (fork tohoto repa) →
vlož proměnné z `.env.example` → Generate Domain. Webhook se zaregistruje
automaticky.

**Docker (VPS, NAS, Raspberry Pi):**
```bash
cp .env.example .env   # vyplň klíče + PUBLIC_URL
docker compose up -d
```

### 6. Po nasazení
1. Pošli botovi `/id` → vrátí tvoje Telegram ID
2. Nastav `TELEGRAM_ALLOWED_USERS=<tvoje_id>` — jinak může bota používat
   kdokoliv a čerpat tvůj API kredit
3. Mapa: `https://tvoje-instance/map?token=MAP_TOKEN`

Detailní technická dokumentace: [CLAUDE.md](CLAUDE.md) · plán featur:
[ROADMAP.md](ROADMAP.md) · změny: [CHANGELOG.md](CHANGELOG.md)

## Příkazy bota

- pošli URL videa → uloží místo
- pošli svoji polohu (Telegram attachment Location) → nejbližší uložená místa
- `/hledej <text>` (alias `/search`) — hledání v uložených místech
- `/zkontroluj` (alias `/dedup`) — kontrola duplicitních míst
- `/id` — tvoje Telegram user ID (pro nastavení whitelistu)
- `/help` (aliasy `/start`, `/napoveda`) — vypíše všechny příkazy

Příkazy se také registrují do menu Telegramu (nabídka po napsání `/`
v chatu), v jazyce podle `BOT_LANGUAGE`.

## Vývoj a testy

```bash
pip install -r requirements-dev.txt
pytest          # testy (běží bez reálných API klíčů)
ruff check .    # lint
```

Obojí automaticky kontroluje GitHub Actions na každý push a pull request.

## Známé limity

- **Instagram vyžaduje cookies.** Z datacenter IP (Railway apod.) Instagram
  anonymní stahování většinou blokuje („login required"). Řešení: exportuj
  cookies přihlášeného účtu (rozšíření typu *Get cookies.txt*) a nastav
  `INSTAGRAM_COOKIES` (obsah souboru) nebo `COOKIES_FILE` (cesta k souboru).
  Cookies občas vyprší a je potřeba je obnovit.
- **Facebook občas blokuje datacenter IP.** Většinou funguje anonymně, ale
  při blokaci pomůže stejný postup s cookies. Stav instance zjistíš na
  endpointu `/debug?token=MAP_TOKEN`.
- **YouTube ze serveru často vyžaduje cookies.** Datacenter IP YouTube běžně
  blokuje hláškou „Sign in to confirm you're not a bot". Řešení je stejné
  jako u Instagramu — do souboru s cookies přidej i cookies přihlášeného
  YouTube/Google účtu (jeden `cookies.txt` může obsahovat obě domény;
  proměnná se jmenuje `INSTAGRAM_COOKIES` z historických důvodů, obsah
  platí pro všechny domény v souboru).
- **TikTok zatím bez ověření provozem.** yt-dlp TikTok podporuje (včetně
  `vm.tiktok.com` share linků) a stahuje anonymně; spolehlivost z datacenter
  IP se může měnit podle anti-bot opatření TikToku. Kdyby stahování selhávalo,
  založ issue s chybovou hláškou z odpovědi bota.
- **Gemini free tier má rate limity.** Při rychlém posílání více videí za
  sebou může analýza dočasně selhat — chvíli počkej a pošli video znovu.
- **Délka videa.** Bot je stavěný na krátká videa (Reels, TikTok, Shorts).
  Videa delší než 10 minut odmítne ještě před stažením — limit jde změnit
  proměnnou `MAX_VIDEO_MINUTES` (0 = bez limitu). I u povolených delších
  videí může zpracování v Gemini vypršet (čeká se max. 2 minuty).
- **Souřadnice bez `GOOGLE_MAPS_API_KEY` jsou jen odhad.** Gemini souřadnice
  odhaduje a může se splést i o kilometry; s Places API klíčem se místo
  dohledá přesně.
- **Změna `BOT_LANGUAGE` / `CATEGORIES` nemění stará data.** Dřív uložené
  řádky zůstávají v původním jazyce a s původními kategoriemi; na mapě se
  kategorie mimo aktuální konfiguraci zobrazí šedě.

## Právní upozornění

Tento nástroj stahuje videa z Facebooku a Instagramu pomocí
[yt-dlp](https://github.com/yt-dlp/yt-dlp), což může porušovat podmínky
služeb společnosti Meta. Nástroj je určen výhradně k **osobní archivaci**
obsahu pro vlastní potřebu (uložení tipů na výlety). Používáš ho na vlastní
odpovědnost. Nestahuj ani nešiř cizí obsah způsobem, který porušuje autorská
práva jeho tvůrců.

## Licence

Kód je dostupný pod licencí [MIT](LICENSE).

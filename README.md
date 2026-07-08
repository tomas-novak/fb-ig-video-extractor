# FB/IG Video Extractor — Cestovní deník přes Telegram

Pošli URL Facebook nebo Instagram Reels **svému** Telegram botovi → AI
automaticky vytáhne místo, přepíše zvuk a uloží vše do Google Sheets.
Uložená místa pak vidíš na interaktivní mapě s filtry.

Jde o **self-hosted** nástroj: každý si nasazuje vlastní instanci s vlastním
botem, vlastní tabulkou a vlastními API klíči. Neexistuje žádný sdílený
veřejný bot.

## Motivace

Při scrollování sociálních sítí narážím na zajímavá místa ve videích (koupaliště,
výlety, restaurace...). Chci je jednoduše uložit z telefonu bez ručního vyplňování.

## Jak to funguje

1. Najdeš zajímavé video na Facebooku nebo Instagramu
2. Klikneš "Sdílet" → zkopíruješ URL → pošleš svému botovi v Telegramu
3. Bot do ~30 sekund odpoví:
   ```
   ✅ Uloženo!
   📍 Koupaliště Slaný
   🏷️ koupání | outdoor, s dětmi, bazén

   Moderní aquapark v Slaném s bazény pro děti i dospělé.
   Zábava pro celou rodinu.
   🧭 https://www.google.com/maps/place/?q=place_id:...
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

### 4. Volitelné klíče
- `GOOGLE_MAPS_API_KEY` — přesné souřadnice míst (Places API New; bez něj se
  použijí odhady AI)
- `ANTHROPIC_API_KEY` — kontrola duplicitních míst příkazem `/zkontroluj`
- `MAP_TOKEN` — ochrana mapy (bez něj je mapa veřejná)
- `WEBHOOK_SECRET` — ověřování Telegram webhooků

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
[ROADMAP.md](ROADMAP.md)

## Právní upozornění

Tento nástroj stahuje videa z Facebooku a Instagramu pomocí
[yt-dlp](https://github.com/yt-dlp/yt-dlp), což může porušovat podmínky
služeb společnosti Meta. Nástroj je určen výhradně k **osobní archivaci**
obsahu pro vlastní potřebu (uložení tipů na výlety). Používáš ho na vlastní
odpovědnost. Nestahuj ani nešiř cizí obsah způsobem, který porušuje autorská
práva jeho tvůrců.

## Licence

Kód je dostupný pod licencí [MIT](LICENSE).

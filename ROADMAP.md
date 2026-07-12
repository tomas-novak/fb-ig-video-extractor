# Roadmap — cesta k úspěšnému open-source projektu

Plán úprav a nových featur seřazený podle dopadu. Cíl: aby si projekt lidé na
GitHubu všimli, dokázali ho rozjet a měli důvod ho používat.

---

## Fáze 0 — Připravenost na zveřejnění

Nutný základ před tím, než má smysl repo propagovat.

- [x] **Přidat `LICENSE` (MIT)** — standardní MIT text s copyright hláškou
  (jméno + rok). GitHub licenci automaticky detekuje a zobrazí v hlavičce repa.
- [x] **Sekce `## Licence` v README** — jedna věta s odkazem na LICENSE.
- [x] **Právní disclaimer do README** — stahování videí přes yt-dlp porušuje
  podmínky služeb Meta. Napsat jasně: nástroj slouží k osobní archivaci,
  používání na vlastní odpovědnost.
- [x] **Vyjasnit self-hosted povahu** — README teď zve čtenáře k použití
  soukromého bota. Přeformulovat na „svého bota" (každý si nasazuje vlastní
  instanci s vlastním Sheetem a vlastními klíči). Zvážit whitelist povolených
  Telegram user ID v kódu, aby cizí lidé nečerpali Gemini kredit.
  *(hotovo: `TELEGRAM_ALLOWED_USERS` + příkaz `/id`, fail-closed validace)*
- [x] **Opravit placeholder v `.env.example`** — `AIzaSy_your_gemini_api_key_here`
  začíná skutečným prefixem Google klíčů a secret-scannery ho falešně hlásí.
  Přepsat na neutrální `your_gemini_api_key_here`.
- [x] **BLOCKER: chránit mutační endpointy mapy** — `POST /delete` a
  `POST /visited` nemají žádnou autentizaci; kdokoliv, kdo zjistí URL instance,
  může mazat data. `GET /data` navíc veřejně vydává celou databázi míst.
  *(hotovo: env `MAP_TOKEN`; mapa se otevírá přes `/map?token=...` a token
  předává na `/data`, `/visited` i `/delete`; server ověřuje konstantním
  porovnáním. Prázdný `MAP_TOKEN` = mapa veřejná — vědomá volba self-hostera.)*

---

## Fáze 1 — Demo, které prodává

Nejvyšší poměr dopad/práce. Lidé rozhodují o hvězdičce během pár sekund
scrollování — potřebují vidět, ne číst.

- [ ] **GIF hlavního flow do README** — obrazovka telefonu: vložení URL reelsu
  do Telegramu → odpověď bota s místem, kategorií a shrnutím. Nahrát jako
  screen-recording, převést na GIF (např. přes ffmpeg), vložit hned pod
  nadpis README.
- [ ] **Screenshot mapy** — mapa s piny, zapnutými filtry kategorií a otevřeným
  popupem místa. Ukazuje „co z toho mám" — cílový stav po pár týdnech používání.
- [ ] **Ukázkový výstup v Google Sheets** — screenshot tabulky s několika řádky
  (anonymizovanými / ukázkovými daty).
- [ ] **Veřejná demo mapa (volitelné)** — instance `/map` naplněná ukázkovými
  daty, odkaz z README. Návštěvník si produkt „osahá" bez instalace.

---

## Fáze 2 — Snížit setup z hodiny na minuty

Každý ruční krok odfiltruje část zájemců. Teď jsou potřeba 4 credentials a
ruční registrace webhooku.

- [x] **Automatická registrace webhooku při startu** — místo ručního
  `python main.py --set-webhook` zavolat `setWebhook` v `lifespan` handleru,
  pokud je nastavená env variable `PUBLIC_URL`. Jeden krok setup navíc zmizí.
  *(hotovo: na Railway funguje zcela automaticky přes `RAILWAY_PUBLIC_DOMAIN`,
  jinde přes `PUBLIC_URL`; selhání registrace nebrání startu)*
- [x] **`Dockerfile` + `docker-compose.yml`** — pro self-hostery (VPS, NAS,
  Raspberry Pi). Compose soubor načte `.env`, jediný příkaz: `docker compose up`.
- [ ] **„Deploy on Railway" tlačítko** — Railway template s předdefinovanými
  env variables (názvy + popisky). Uživatel jen vyplní hodnoty ve formuláři.
  *(vyžaduje publikovat template z Railway účtu autora — až po zveřejnění repa)*
- [x] **Setup průvodce v README** — očíslovaný postup se všemi kroky:
  1. BotFather → token (2 min)
  2. Google AI Studio → Gemini klíč (2 min)
  3. Google Cloud → service account + sdílení Sheetu (5–10 min, nejtěžší krok
     — doplnit screenshoty)
  4. Deploy (Railway tlačítko nebo Docker)

  Uvést odhad celkového času („~15 minut, vše zdarma") — snižuje bariéru.
- [ ] **Volitelný SQLite backend (odvážnější krok)** — service account pro
  Sheets je nejotravnější credential. Abstrahovat `sheets.py` na jednoduché
  storage rozhraní (append řádku, čtení všech, update buňky) a přidat SQLite
  implementaci. Se SQLite stačí 2 klíče (Telegram + Gemini) a setup je
  triviální. Sheets zůstává jako výchozí varianta pro ne-programátory.

---

## Fáze 3 — Angličtina a konfigurovatelnost

Český GitHub trh je malý. Otevření světu = násobně větší dosah.

- [x] **Anglické README jako výchozí** — `README.md` anglicky, česká verze
  vedle jako `README.cs.md` (vzájemné odkazy v hlavičce).
- [x] **Jazyk odpovědí bota do konfigurace** — env variable `BOT_LANGUAGE`
  (např. `cs` / `en`). Texty zpráv v `main.py` vytáhnout do slovníku,
  Gemini promptu v `analyzer.py` předat instrukci, v jakém jazyce psát
  shrnutí a přepis.
  *(hotovo: `i18n.py` – katalog textů cs/en, dvoujazyčné Gemini prompty,
  přeložená mapa i zdůvodnění duplicit; přepis zůstává v jazyce videa.
  Anglické aliasy příkazů `/search` a `/dedup` fungují vždy.)*
- [x] **Kategorie do konfigurace** — kategorie (`koupání`, `turistika`, …)
  jsou natvrdo v promptu a mapě. Vytáhnout do env variable
  (`CATEGORIES=swimming,hiking,food,...`) nebo config souboru; prompt i
  filtry na mapě je načtou odtud.
  *(hotovo: `CATEGORIES` v `i18n.py`, výchozí sada podle jazyka; poslední
  kategorie je záchytná. Mapa přiděluje barvy podle pořadí v konfiguraci,
  kategorie mimo konfiguraci – starší data – zobrazí šedě.)*

---

## Fáze 4 — TikTok a YouTube Shorts

Use-case „místa z krátkých videí" žije nejvíc na TikToku. yt-dlp obě platformy
už umí — jde převážně o povolení URL formátů.

- [x] **TikTok** — přidat rozpoznání `tiktok.com` URL (včetně krátkých
  `vm.tiktok.com` share linků) do validace v `main.py` / `extractor.py`.
  Otestovat, zda yt-dlp z datacenter IP stahuje spolehlivě; případné limity
  zdokumentovat.
  *(hotovo v kódu; spolehlivost z datacenter IP zbývá ověřit provozem —
  poznámka v README / Známé limity)*
- [x] **YouTube Shorts** — povolit `youtube.com/shorts/ID` URL. Pozor na
  YouTube anti-bot opatření na datacenter IP — zdokumentovat případnou
  potřebu cookies.
  *(hotovo: cookies se pro YouTube posílají stejně jako pro Instagram,
  anti-bot blokace má vlastní srozumitelnou hlášku bota + popis v README)*
- [x] **Sloupec `L: Zdroj` rozšířit** o nové hodnoty (tiktok, youtube), aby
  fungovaly filtry.
  *(hotovo: `extract_source()` je jediné místo určování zdroje — analyzer
  ho nově používá místo vlastní FB/IG podmínky)*

---

## Fáze 5 — Z archivu produkt na cesty

Featury, které promění pasivní sbírku míst v nástroj používaný přímo na výletě.

- [x] **„Místa poblíž"** — uživatel pošle botu polohu (Telegram attachment
  Location) → bot vrátí uložená místa do X km, seřazená podle vzdálenosti,
  s odkazem na navigaci. Souřadnice v tabulce už jsou, výpočet vzdálenosti
  (haversine) je pár řádků. Killer feature: použiješ ji, když někde reálně jsi.
  *(hotovo: 5 nejbližších nenavštívených míst do 50 km, sloučené skupiny
  jednou; když v okruhu nic není, ukáže aspoň nejbližší místo)*
- [x] **Sdílení mapy** — read-only odkaz na `/map` pro partnera/kamarády při
  plánování. Zvážit jednoduchý token v URL, aby mapa nebyla úplně veřejná
  (skrývá i tlačítka mazání/visited pro cizí návštěvníky).
  *(hotovo: `MAP_VIEW_TOKEN` – server mutace zamítá, mapa tlačítka skryje
  podle hlavičky X-Can-Edit)*
- [x] **Export dat** — endpoint `/export` s formáty GeoJSON, GPX a KML.
  Umožní import pinů do Mapy.cz, Organic Maps nebo Google My Maps.
  Signalizuje „tvá data ti patří" — cestovatelská komunita to oceňuje.
  *(hotovo: `/export?format=geojson|gpx|kml`, odkazy přímo v panelu mapy;
  jedno místo na skupinu, včetně všech video URL)*
- [x] **Vyhledávání v Telegramu (volitelné)** — příkaz `/hledej <text>`
  prohledá názvy míst, tagy a shrnutí, vrátí pár nejlepších shod s odkazy.
  *(hotovo: bez diakritiky – „hriste" najde „hřiště"; navštívená označena ✅)*

---

## Fáze 6 — Důvěryhodnost

Nepřinese nové uživatele, ale zvedá konverzi těch, kteří už přišli.

- [x] **Základní testy** — aspoň pro čisté funkce: validace URL, parsování
  Gemini odpovědi, dedup logika. `pytest`, bez nutnosti reálných API klíčů
  (mock).
  *(hotovo: 108 testů ve `tests/` — URL/příkazy/whitelist, parsování Gemini
  i Claude odpovědí, dedup předfiltr, /hledej, místa poblíž, export
  GeoJSON/GPX/KML, parsování řádků tabulky; `pip install -r
  requirements-dev.txt && pytest`)*
- [x] **GitHub Actions CI** — spustit testy + `ruff` lint na každý push,
  badge do README.
  *(hotovo: `.github/workflows/ci.yml`, ruff konfigurace v `pyproject.toml`)*
- [x] **Sekce „Známé limity" v README** — FB občas blokuje datacenter IP;
  popsat řešení přes cookies (`--cookies` v yt-dlp), rate limity Gemini
  free tieru, max. délku videa.
- [x] **CHANGELOG.md** — od prvního veřejného release vést stručný log změn.
  *(založen; do prvního release se změny evidují pod „Nevydáno")*

---

## Doporučené pořadí na první týden

1. Fáze 0 celá (pár hodin, odblokuje zveřejnění)
2. Fáze 1: GIF + screenshoty (nejvyšší dopad na hvězdičky)
3. Fáze 2: Docker + auto-webhook
4. Fáze 3: anglické README

„Místa poblíž" z Fáze 5 stojí za to udělat hned bez ohledu na GitHub — je
užitečná pro vlastní používání. Zbytek Fáze 5 a SQLite backend přidávat až
podle reálného zájmu uživatelů.

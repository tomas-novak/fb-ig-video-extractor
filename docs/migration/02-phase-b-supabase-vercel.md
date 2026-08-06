# Fáze B — Supabase + mapa na Vercelu (návrh)

> **Stav: návrh k odsouhlasení, ne runbook.** Provádí se až po tom, co Fáze A
> pár dní stabilně poběží. Po Fázi A je systém plně funkční — tahle fáze je
> vylepšení, ne nutnost.

---

## Proč vůbec

Google Sheets funguje jako databáze překvapivě dobře, ale při každé operaci se
načítá **celá tabulka** (`get_all_values()` v `sheets.py`). Zpracování jednoho
videa dnes čte tabulku třikrát — s rostoucím počtem míst to bude čím dál
pomalejší.

Druhá věc: primárním klíčem je **číslo řádku**. Používá ho mapa, mazání,
označení „navštíveno" i slučování duplicit. Když se řádek mezitím smaže, čísla
se posunou a operace může trefit jiné místo.

A do třetice: mapa je dnes jeden velký HTML string v `map_page.py`, servírovaný
botem. Jako samostatná aplikace se bude líp vyvíjet a odlehčí to serveru.

Migrace na Supabase je navíc už dlouho v `CLAUDE.md` mezi budoucími rozšířeními.

## Co se nemění

- Bot zůstává na VPS (potřebuje ffmpeg a dlouhoběžící proces — to Supabase
  ani Vercel nenahradí).
- Telegram komunikace, příkazy, zpracování videa i Gemini analýza beze změny.
- Google Sheets **se nemaže** — zůstává jako záloha, jen se do něj přestane
  zapisovat.

---

## B1. Schéma v Supabase

Nový soubor `supabase/schema.sql`. Tabulka `videos` odpovídá dnešním 18
sloupcům (`sheets.py`, `models.py:to_sheets_row`), ale se skutečnými typy:

| Dnes (Sheets) | Nově (Postgres) |
|---|---|
| číslo řádku | `id bigint generated always as identity primary key` |
| A datum (text) | `created_at timestamptz` |
| B url | `url text` |
| C autor | `author text` |
| D titulek | `title text` |
| E místo | `location_name text` |
| F, G lat/lng (text) | `lat double precision`, `lng double precision` |
| H kategorie | `category text` |
| I tagy (čárkou oddělené) | `tags text[]` |
| J shrnutí | `summary text` |
| K přepis | `transcript text` |
| L zdroj | `source text` |
| M group_id | `group_id text` |
| N video_id | `video_id text` |
| O navštíveno ("ano"/prázdné) | `visited boolean` |
| P place_id | `place_id text` |
| Q maps_url | `maps_url text` |
| R geo_source | `geo_source text` |

Indexy na `video_id`, `url`, `place_id`, `group_id` (podle nich se dnes
vyhledává). Rozšíření `cube` + `earthdistance` (nebo PostGIS) kvůli dvěma
dotazům, které dnes běží v Pythonu nad celou tabulkou:

- kandidáti na duplicitu do 8 km (`dedup.py`),
- nejbližší nenavštívená místa při poslání polohy do Telegramu (`main.py`).

**Zabezpečení (RLS):** anon key umí jen číst (to je ten, se kterým poběží mapa
na Vercelu), zápisy jen přes service-role key, který má výhradně bot na VPS.

---

## B2. Datová vrstva bota

Nový modul `db.py` se **stejným rozhraním jako dnešní `sheets.py`**:
`append_row`, `read_rows`, `find_duplicate`, `find_by_place_id`,
`set_group_ids`, `set_visited`, `delete_place_rows`, `new_group_id`.

Díky tomu je změna v `main.py` v zásadě jen výměna importu — a rollback taky.

Co se musí projít ručně:

- **Čísla řádků → `id`.** Dotčené je callback data u tlačítek pro slučování
  (`merge:<a>:<b>` v `handle_callback`), endpointy `POST /visited`,
  `POST /delete` a výstup `GET /data`.
- **`/search`** — dnes čte celou tabulku a filtruje v Pythonu; nově `ilike`
  nebo fulltext přímo v Postgresu.
- **`dedup.py`** — dnešní O(n²) porovnávání všech dvojic nahradí SQL dotaz na
  dvojice do 8 km. Posuzování přes Claude Haiku zůstává beze změny.
- **Testy** — `tests/test_sheets.py` → `tests/test_db.py` s mockem Supabase.

**Migrační skript** `migrate_sheets_to_supabase.py`: přečte data stávající
funkcí `read_rows()`, vloží je do Supabase a na konci vypíše porovnání počtu
záznamů. Spouští se jednou, ručně.

---

## B3. Mapa na Vercelu

Nový adresář `map/` — statická stránka vycházející z dnešního `map_page.py`
(Leaflet, filtry podle kategorií a tagů, režim navštíveno). Rozdíl:

- **Čtení dat** jde přímo do Supabase REST s anon keyem, ne přes `/data` bota.
- **Zápisy** (navštíveno, mazání, slučování) jdou dál na bota na VPS — endpointy
  dostanou CORS pro doménu mapy a token se předává stejně jako dnes
  (`withToken()` v `map_page.py`).

Nasazení jako statický projekt na Vercelu; URL Supabase a anon key se vloží
při buildu.

`/map` na botovi zůstane funkční jako záloha; po ověření může přesměrovávat
na Vercel.

---

## Postup

1. Založit Supabase projekt, spustit `schema.sql`
2. Spustit migrační skript, ověřit počty záznamů
3. Nasadit `db.py`, přepnout import, `pytest`
4. Ověřit e2e: nové video → záznam v Supabase; `/hledej`, `/zkontroluj`,
   tlačítka pro sloučení
5. Nasadit mapu na Vercel, porovnat piny se starou `/map`
6. Vypnout zápisy do Sheets (nechat jako zálohu)

## Ověření

- Počet záznamů v Supabase odpovídá počtu řádků v Sheets
- `pytest` prochází
- Nové video projde celým řetězcem a objeví se na mapě
- Mapa na Vercelu ukazuje stejné piny jako `/map`; navštíveno i mazání fungují

## Na co si dát pozor

- **Free tier Supabase pauzuje projekt po ~7 dnech nečinnosti.** Denní provoz
  bota to udrží aktivní, ale je dobré o tom vědět.
- **Tlačítka pro slučování odeslaná před přepnutím přestanou platit**, protože
  se mění identifikátory. Nic se nerozbije, stačí poslat `/zkontroluj` znovu.
- **Rollback** je popsaný v [`03-rollback.md`](03-rollback.md) — v zásadě vrátit
  import na `sheets` a restartovat, dokud je Sheets aktuální.
- Lokální PostgreSQL na VPS (port 5432) patří Hermesovi a **není** pro tohle
  vhodný — mapa na Vercelu potřebuje databázi dostupnou z internetu.

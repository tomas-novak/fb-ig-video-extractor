# CLAUDE.md — FB/IG Video Extractor

## Co tento projekt dělá

Telegram bot, který přijme URL Facebook Reels nebo Instagram Reels, automaticky
vytáhne obsah videa, přepíše zvuk, extrahuje místo a uloží metadata do Google Sheets.

## Architektura

```
Uživatel (telefon)
  → pošle URL do Telegram botu
      → Python API (Railway)
          → yt-dlp stáhne VIDEO (ne audio – FB datacentru audio-only stream nenabízí)
          → Gemini Flash analyzuje video: přepis zvuku + text na obrazovce + popisek (jedno volání)
          → Google Sheets API uloží řádek
          → Telegram Bot API odpoví uživateli
```

Pozn.: Posíláme Gemini celé video (ne extrahovaný zvuk). Důvod: na datacenter IP
Facebook nenabízí samostatný audio stream, jen video. Gemini navíc čte text
zobrazený ve videu, což zpřesňuje určení místa.

## Stack

- **Runtime**: Python 3.11+
- **Web framework**: FastAPI + uvicorn
- **Telegram**: python-telegram-bot nebo přímé volání Bot API
- **Video download**: yt-dlp (formát `hd/sd/best`)
- **AI (analýza videa)**: Google Gemini 2.5 Flash (multimodální video – zvuk + obraz)
- **Databáze**: Google Sheets (google-auth + gspread)
- **Hosting**: Railway (region EU-West)

## Klíčové soubory

```
FB_IG_video_extractor/
├── CLAUDE.md          # tento soubor
├── README.md          # uživatelská dokumentace
├── main.py            # FastAPI app + Telegram webhook handler
├── extractor.py       # yt-dlp download logic
├── analyzer.py        # Gemini API volání (transkripce + analýza)
├── sheets.py          # Google Sheets zápis
├── models.py          # datové modely (VideoMetadata)
├── requirements.txt
├── railway.toml       # Railway deploy config
└── .env.example       # vzor environment variables
```

## Environment variables

```
TELEGRAM_BOT_TOKEN=       # token z @BotFather
GEMINI_API_KEY=           # Google AI Studio
GOOGLE_SHEETS_ID=         # ID Google Sheetu
GOOGLE_SERVICE_ACCOUNT=   # JSON service account (base64 nebo path)
WEBHOOK_SECRET=           # volitelný secret pro ověření Telegram webhooků
```

## Google Sheets struktura (Sheet1)

| A: Datum | B: URL | C: Autor | D: Titulek | E: Místo | F: Lat | G: Lng | H: Kategorie | I: Tagy | J: Shrnutí | K: Přepis | L: Zdroj |

Oproti původní Make.com verzi přibyl sloupec **K: Přepis** — ukládá plný text transkripce.

## Podporované URL formáty

- `https://www.facebook.com/reel/ID`
- `https://www.instagram.com/reel/ID`
- `https://www.instagram.com/p/ID`
- Share linky (zkrácené) — yt-dlp je automaticky rozbalí

## Kategorie (pro filtrování v mapě)

`koupání` · `turistika` · `jídlo` · `kultura` · `příroda` · `sport` · `zábava` · `jiné`

## Vývoj

```bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env        # vyplnit hodnoty
uvicorn main:app --reload --port 8000
```

## Nasazení (Railway)

1. `git push` na GitHub repo
2. Railway automaticky detekuje Python a nasadí
3. Nastavit env variables v Railway dashboard
4. Spustit `python main.py --set-webhook` pro registraci Telegram webhooku

## Budoucí rozšíření

- Google My Maps integrace (zobrazení pinů z Sheets)
- Filtrování mapy podle kategorie
- Migrace databáze na Supabase pro lepší dotazování
- Podpora YouTube Shorts

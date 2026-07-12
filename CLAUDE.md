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
├── README.md          # uživatelská dokumentace (anglicky, výchozí)
├── README.cs.md       # uživatelská dokumentace (česky)
├── main.py            # FastAPI app + Telegram webhook handler
├── extractor.py       # yt-dlp download logic
├── analyzer.py        # Gemini API volání (transkripce + analýza)
├── i18n.py            # jazyk bota (BOT_LANGUAGE) + kategorie (CATEGORIES) + texty
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
BOT_LANGUAGE=             # jazyk odpovědí bota, mapy a AI shrnutí: cs (výchozí) / en
CATEGORIES=               # vlastní kategorie oddělené čárkou; poslední = záchytná
```

## Google Sheets struktura (Sheet1)

| A: Datum | B: URL | C: Autor | D: Titulek | E: Místo | F: Lat | G: Lng | H: Kategorie | I: Tagy | J: Shrnutí | K: Přepis | L: Zdroj | M: group_id |

**M: group_id** — místa se stejným group_id se na mapě zobrazí jako jeden pin s více videi.
Slučování navrhuje Claude Haiku (příkaz `/zkontroluj` v Telegramu → tlačítka Sloučit/Ponechat).
Viz `dedup.py`. Sloučení nic nemaže a je vratné (smazat group_id v tabulce).

## Podporované URL formáty

- `https://www.facebook.com/reel/ID`
- `https://www.instagram.com/reel/ID`
- `https://www.instagram.com/p/ID`
- `https://www.tiktok.com/@user/video/ID`
- `https://www.youtube.com/shorts/ID`
- Share linky (zkrácené: `fb.watch`, `vm.tiktok.com`, `youtu.be`) — yt-dlp je automaticky rozbalí

## Kategorie (pro filtrování v mapě)

Výchozí (cs): `koupání` · `turistika` · `jídlo` · `kultura` · `příroda` · `sport` · `zábava` · `hotel` · `jiné`

Kategorie jsou konfigurovatelné env proměnnou `CATEGORIES` (viz `i18n.py`);
poslední v seznamu je záchytná. Jazyk odpovědí bota, mapy a Gemini shrnutí
řídí `BOT_LANGUAGE` (`cs`/`en`); přepis zvuku zůstává v jazyce videa.

## Vývoj

```bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env        # vyplnit hodnoty
uvicorn main:app --reload --port 8000
```

## Git

- Commit messages, názvy větví a texty PR piš **anglicky**.
- Komentáře v kódu a dokumentace pro vývoj (tento soubor) zůstávají česky.

## Nasazení (Railway)

1. `git push` na GitHub repo
2. Railway automaticky detekuje Python a nasadí
3. Nastavit env variables v Railway dashboard
4. Spustit `python main.py --set-webhook` pro registraci Telegram webhooku

## Budoucí rozšíření

- Google My Maps integrace (zobrazení pinů z Sheets)
- Filtrování mapy podle kategorie
- Migrace databáze na Supabase pro lepší dotazování

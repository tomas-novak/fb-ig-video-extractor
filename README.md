# FB/IG Video Extractor — Cestovní deník přes Telegram

Pošli URL Facebook nebo Instagram Reels do Telegram botu → AI automaticky
vytáhne místo, přepíše zvuk a uloží vše do Google Sheets.

## Motivace

Při scrollování sociálních sítí narážím na zajímavá místa ve videích (koupaliště,
výlety, restaurace...). Chci je jednoduše uložit z telefonu bez ručního vyplňování.

## Jak to funguje

1. Najdeš zajímavé video na Facebooku nebo Instagramu
2. Klikneš "Sdílet" → zkopíruješ URL → pošleš do Telegram botu `@VyljetyBot`
3. Bot do 30 sekund odpoví:
   ```
   ✅ Uloženo!
   📍 Koupaliště Slaný
   🏷️ koupání | outdoor, s dětmi, bazén
   
   Moderní aquapark v Slaném s bazény pro děti i dospělé.
   Zábava pro celou rodinu.
   ```
4. Místo se uloží do Google Sheets včetně GPS souřadnic a přepisu zvuku

## Výsledek v Google Sheets

Tabulka obsahuje všechna uložená místa s GPS souřadnicemi, kategoriemi
a plným přepisem mluveného slova z videa.

## Technologie

- Telegram Bot API (vstupní rozhraní z mobilu)
- yt-dlp (stažení videa)
- Google Gemini Flash (přepis zvuku + analýza místa)
- Google Sheets (databáze míst)
- FastAPI + Railway (backend hosting)

## Nastavení (pro vývojáře)

Viz [CLAUDE.md](CLAUDE.md) pro detailní technickou dokumentaci.

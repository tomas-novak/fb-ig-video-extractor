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

## Nastavení (pro vývojáře)

Viz [CLAUDE.md](CLAUDE.md) pro detailní technickou dokumentaci a
[ROADMAP.md](ROADMAP.md) pro plánované featury.

Po nasazení doporučujeme nastavit `TELEGRAM_ALLOWED_USERS` (čárkou oddělená
Telegram user ID), aby bota nemohl používat nikdo cizí a čerpat tvůj API
kredit. Svoje ID zjistíš příkazem `/id` poslaným botovi.

## Právní upozornění

Tento nástroj stahuje videa z Facebooku a Instagramu pomocí
[yt-dlp](https://github.com/yt-dlp/yt-dlp), což může porušovat podmínky
služeb společnosti Meta. Nástroj je určen výhradně k **osobní archivaci**
obsahu pro vlastní potřebu (uložení tipů na výlety). Používáš ho na vlastní
odpovědnost. Nestahuj ani nešiř cizí obsah způsobem, který porušuje autorská
práva jeho tvůrců.

## Licence

Kód je dostupný pod licencí [MIT](LICENSE).

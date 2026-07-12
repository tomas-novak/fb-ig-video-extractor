"""Jazyk bota (BOT_LANGUAGE) a konfigurovatelné kategorie (CATEGORIES).

BOT_LANGUAGE: `en` (výchozí) nebo `cs` – jazyk odpovědí bota, mapy,
Gemini shrnutí a zdůvodnění duplicit. Přepis mluveného slova (transcript)
zůstává vždy v původním jazyce videa.

CATEGORIES: čárkou oddělený seznam kategorií; přepisuje výchozí sadu.
Poslední kategorie v seznamu je záchytná („jiné“ / „other“) – použije se,
když AI žádnou kategorii neurčí.
"""
import os

SUPPORTED_LANGUAGES = ("cs", "en")


def _parse_language(raw: str) -> str:
    """Fail closed: překlep v BOT_LANGUAGE je chyba konfigurace – radši
    spadnout při startu než tiše odpovídat jiným jazykem, než uživatel čeká."""
    lang = raw.strip().lower()
    if not lang:
        return "en"
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"BOT_LANGUAGE={raw!r} is not a supported language – "
            f"allowed values: {', '.join(SUPPORTED_LANGUAGES)}"
        )
    return lang


LANG = _parse_language(os.getenv("BOT_LANGUAGE", ""))

DEFAULT_CATEGORIES = {
    "cs": ["koupání", "turistika", "jídlo", "kultura", "příroda",
           "sport", "zábava", "hotel", "jiné"],
    "en": ["swimming", "hiking", "food", "culture", "nature",
           "sport", "fun", "hotel", "other"],
}


def _parse_categories(raw: str, lang: str) -> list[str]:
    """Fail closed: duplicitní kategorie by rozbily filtry na mapě."""
    cats = [c.strip() for c in raw.split(",") if c.strip()]
    if not cats:
        return list(DEFAULT_CATEGORIES[lang])
    duplicates = {c for c in cats if cats.count(c) > 1}
    if duplicates:
        raise ValueError(f"CATEGORIES contains duplicate items: {sorted(duplicates)}")
    return cats


CATEGORIES = _parse_categories(os.getenv("CATEGORIES", ""), LANG)
# Záchytná kategorie – poslední v seznamu (výchozí „jiné“ / „other“)
FALLBACK_CATEGORY = CATEGORIES[-1]


MESSAGES = {
    "cs": {
        # Srozumitelné chybové hlášky (friendly_error)
        "err_photo": "📷 Tohle vypadá jako fotka nebo série fotek (carousel), ne video. "
                     "Pošli mi prosím odkaz na video nebo reel.",
        "err_login": "🔒 Nepodařilo se dostat k obsahu (Instagram nejspíš vyžaduje přihlášení "
                     "nebo vypršely cookies). U Facebook odkazů to funguje vždy.",
        "err_unsupported": "🤔 Tenhle odkaz neumím zpracovat. Podporuju Facebook a Instagram "
                           "videa/reels, TikTok a YouTube Shorts.",
        "err_too_long": "⏱️ {err}. Bot je stavěný na krátká videa (Reels, TikTok, Shorts).",
        "err_youtube_bot": "🤖 YouTube blokuje stahování ze serveru (anti-bot ochrana). "
                           "Pomůže nastavit cookies přihlášeného účtu – viz Známé limity v README.",
        "err_no_audio": "🔇 Z videa se nepodařilo získat zvukovou stopu (možná nemá zvuk). "
                        "Zkus prosím jiné video.",
        "err_generic": "❌ Něco se nepovedlo: {err}",
        "err_video_too_long": "video je příliš dlouhé ({minutes:.0f} min, limit {limit} min)",
        "gemini_not_processed": "Gemini nezpracoval video (stav {state})",
        "gemini_no_text": "Gemini nevrátil žádný text k analýze ({error})",

        # Webhook / příkazy
        "id_reply": "🆔 Tvoje Telegram user ID: {user_id}",
        "private_bot": "⛔ Tento bot je soukromý. Pokud je tvůj, přidej si "
                       "svoje ID ({user_id}) do TELEGRAM_ALLOWED_USERS.",
        "search_usage": "Použití: /hledej <text>\nnapř. /hledej tobogán",
        "dedup_started": "🔍 Kontroluji duplicitní místa, chvíli počkej...",
        "help": "Pošli mi URL videa – Facebook/Instagram Reels, "
                "TikTok nebo YouTube Shorts.\n"
                "📎 Pošli mi svoji polohu a najdu uložená místa poblíž.\n"
                "/hledej <text> – hledání v uložených místech\n"
                "/zkontroluj – kontrola duplicitních míst",

        # Zpracování videa
        "dup_saved": "⚠️ Tohle video už máš uložené:\n📍 {name} ({date})",
        "dup_saved_other": "⚠️ Tohle video už máš uložené (pod jiným odkazem):\n"
                           "📍 {name} ({date})",
        "processing": "⏳ Zpracovávám video, chvíli počkej...",
        "group_note": "\n🔗 Přidáno k existujícímu místu „{name}“.",
        "precision_note": "\n⚠️ Poloha je jen odhad (místo se nepodařilo najít na Google Maps).",
        "saved": "✅ Uloženo!\n📍 {name}\n🏷️ {category} | {tags}\n\n"
                 "{summary}\n🧭 {maps_url}{precision}{group_note}",

        # /hledej
        "search_none": "🔍 Pro „{query}“ jsem nic nenašel.",
        "search_header": "🔍 Nalezeno pro „{query}“:",
        "search_failed": "❌ Hledání selhalo: {error}",

        # Místa poblíž
        "nearby_none_saved": "Nemáš uložená žádná nenavštívená místa.",
        "nearby_nothing": "V okruhu {radius} km nemáš nic uloženo. Nejblíž je:\n"
                          "📍 {name} ({dist:.0f} km)\n🧭 {url}",
        "nearby_header": "📍 Nejbližší uložená místa ({count}):",

        # /zkontroluj + slučování
        "dedup_none": "✅ Žádné duplicitní místo jsem nenašel.",
        "dedup_suggestion": "🤔 Vypadá to na stejné místo:\n\n"
                            "1️⃣ {a_name} ({a_date})\n2️⃣ {b_name} ({b_date})\n\n"
                            "📏 Vzdálenost: {distance:.1f} km\n💡 {reason}",
        "btn_merge": "🔗 Sloučit",
        "btn_keep": "✋ Ponechat zvlášť",
        "dedup_done": "Hotovo – {count} návrh(ů) výše. Rozhodni tlačítky.",
        "dedup_failed": "❌ Kontrola selhala: {error}",
        "cb_kept": "Ponecháno zvlášť",
        "kept_msg": "✋ OK, nechávám jako dvě různá místa.",
        "cb_row_gone": "Řádek už neexistuje",
        "row_gone_msg": "⚠️ Některý z řádků už v tabulce není (možná smazán). "
                        "Spusť /zkontroluj znovu.",
        "cb_merged": "Sloučeno",
        "merged_msg": "🔗 Sloučeno: „{a}“ + „{b}“ se teď na mapě zobrazí jako jedno místo.",
        "cb_error": "Chyba",
        "merge_failed": "❌ Sloučení selhalo: {error}",

        # Dedup (Claude verdikty)
        "dedup_reason_place_id": "Stejné místo podle Google Maps (place_id).",
        "dedup_reason_unparseable": "neparsovatelná odpověď: {raw}",
        # Instrukce pro Claude, v jakém jazyce psát zdůvodnění – vkládá se
        # do českého promptu v dedup.py, proto je česky v obou katalozích.
        "dedup_reason_lang": "česky",

        # Export
        "export_doc_name": "Výlety",
        "export_filename": "vylety",
    },
    "en": {
        "err_photo": "📷 This looks like a photo or a photo carousel, not a video. "
                     "Please send me a link to a video or reel.",
        "err_login": "🔒 Couldn't access the content (Instagram probably requires login "
                     "or the cookies expired). Facebook links always work.",
        "err_unsupported": "🤔 I can't process this link. I support Facebook and Instagram "
                           "videos/reels, TikTok and YouTube Shorts.",
        "err_too_long": "⏱️ {err}. This bot is built for short videos (Reels, TikTok, Shorts).",
        "err_youtube_bot": "🤖 YouTube blocks downloads from servers (anti-bot protection). "
                           "Setting cookies of a logged-in account helps – see Known "
                           "limitations in the README.",
        "err_no_audio": "🔇 Couldn't extract the audio track from the video (it may have "
                        "no sound). Please try another video.",
        "err_generic": "❌ Something went wrong: {err}",
        "err_video_too_long": "video is too long ({minutes:.0f} min, limit {limit} min)",
        "gemini_not_processed": "Gemini failed to process the video (state {state})",
        "gemini_no_text": "Gemini returned no text to analyze ({error})",

        "id_reply": "🆔 Your Telegram user ID: {user_id}",
        "private_bot": "⛔ This bot is private. If it's yours, add your "
                       "ID ({user_id}) to TELEGRAM_ALLOWED_USERS.",
        "search_usage": "Usage: /search <text>\ne.g. /search waterslide",
        "dedup_started": "🔍 Checking for duplicate places, hang on...",
        "help": "Send me a video URL – Facebook/Instagram Reels, "
                "TikTok or YouTube Shorts.\n"
                "📎 Send me your location and I'll find saved places nearby.\n"
                "/search <text> – search your saved places\n"
                "/dedup – check for duplicate places",

        "dup_saved": "⚠️ You already saved this video:\n📍 {name} ({date})",
        "dup_saved_other": "⚠️ You already saved this video (under a different link):\n"
                           "📍 {name} ({date})",
        "processing": "⏳ Processing the video, hang on...",
        "group_note": "\n🔗 Added to existing place “{name}”.",
        "precision_note": "\n⚠️ Location is only an estimate (place not found on Google Maps).",
        "saved": "✅ Saved!\n📍 {name}\n🏷️ {category} | {tags}\n\n"
                 "{summary}\n🧭 {maps_url}{precision}{group_note}",

        "search_none": "🔍 Nothing found for “{query}”.",
        "search_header": "🔍 Results for “{query}”:",
        "search_failed": "❌ Search failed: {error}",

        "nearby_none_saved": "You have no unvisited places saved.",
        "nearby_nothing": "Nothing saved within {radius} km. The closest place is:\n"
                          "📍 {name} ({dist:.0f} km)\n🧭 {url}",
        "nearby_header": "📍 Closest saved places ({count}):",

        "dedup_none": "✅ No duplicate places found.",
        "dedup_suggestion": "🤔 These look like the same place:\n\n"
                            "1️⃣ {a_name} ({a_date})\n2️⃣ {b_name} ({b_date})\n\n"
                            "📏 Distance: {distance:.1f} km\n💡 {reason}",
        "btn_merge": "🔗 Merge",
        "btn_keep": "✋ Keep separate",
        "dedup_done": "Done – {count} suggestion(s) above. Decide with the buttons.",
        "dedup_failed": "❌ Check failed: {error}",
        "cb_kept": "Kept separate",
        "kept_msg": "✋ OK, keeping them as two different places.",
        "cb_row_gone": "Row no longer exists",
        "row_gone_msg": "⚠️ One of the rows is no longer in the sheet (maybe deleted). "
                        "Run /dedup again.",
        "cb_merged": "Merged",
        "merged_msg": "🔗 Merged: “{a}” + “{b}” will now show as one place on the map.",
        "cb_error": "Error",
        "merge_failed": "❌ Merge failed: {error}",

        "dedup_reason_place_id": "Same place according to Google Maps (place_id).",
        "dedup_reason_unparseable": "unparseable response: {raw}",
        # Záměrně česky („anglicky“, ne "in English") – jde o instrukci
        # uvnitř českého promptu pro Claude v dedup.py, ne o text pro uživatele.
        "dedup_reason_lang": "anglicky",

        "export_doc_name": "Trips",
        "export_filename": "trips",
    },
}


def t(key: str, **kwargs) -> str:
    """Vrátí text v jazyce bota; kwargs se dosadí přes str.format()."""
    text = MESSAGES[LANG][key]
    return text.format(**kwargs) if kwargs else text

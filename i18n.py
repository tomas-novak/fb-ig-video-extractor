"""Bot language (BOT_LANGUAGE) and configurable categories (CATEGORIES).

BOT_LANGUAGE: `en` (default) or `cs` – the language of the bot's replies, the
map, Gemini summaries and duplicate reasoning. The speech transcript always
stays in the original language of the video.

CATEGORIES: comma-separated list of categories; overrides the default set.
The last category in the list is the fallback ("jiné" / "other") – used when
the AI does not determine any category.
"""
import os

SUPPORTED_LANGUAGES = ("cs", "en")


def _parse_language(raw: str) -> str:
    """Fail closed: a typo in BOT_LANGUAGE is a configuration error – better to
    crash at startup than to quietly reply in a different language than expected."""
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
    """Fail closed: duplicate categories would break the filters on the map."""
    cats = [c.strip() for c in raw.split(",") if c.strip()]
    if not cats:
        return list(DEFAULT_CATEGORIES[lang])
    duplicates = {c for c in cats if cats.count(c) > 1}
    if duplicates:
        raise ValueError(f"CATEGORIES contains duplicate items: {sorted(duplicates)}")
    return cats


CATEGORIES = _parse_categories(os.getenv("CATEGORIES", ""), LANG)
# Fallback category – the last one in the list (default "jiné" / "other")
FALLBACK_CATEGORY = CATEGORIES[-1]


MESSAGES = {
    "cs": {
        # Human-friendly error messages (friendly_error)
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

        # Webhook / commands
        "id_reply": "🆔 Tvoje Telegram user ID: {user_id}",
        "private_bot": "⛔ Tento bot je soukromý. Pokud je tvůj, přidej si "
                       "svoje ID ({user_id}) do TELEGRAM_ALLOWED_USERS.",
        # {cmd} is filled in by the caller via command_name() from the BOT_COMMANDS registry
        "search_usage": "Použití: {cmd} <text>\nnapř. {cmd} tobogán",
        "dedup_started": "🔍 Kontroluji duplicitní místa, chvíli počkej...",
        # {commands} is filled in by help_text() from the BOT_COMMANDS registry
        "help": "📖 Co umím:\n\n"
                "🎬 Pošli mi URL videa (Facebook/Instagram Reels, TikTok, "
                "YouTube Shorts) – vytáhnu z něj místo a uložím ho do tabulky.\n"
                "📎 Pošli mi svoji polohu a najdu uložená místa poblíž.\n\n"
                "Příkazy:\n{commands}",

        # Video processing
        "dup_saved": "⚠️ Tohle video už máš uložené:\n📍 {name} ({date})",
        "dup_saved_other": "⚠️ Tohle video už máš uložené (pod jiným odkazem):\n"
                           "📍 {name} ({date})",
        "processing": "⏳ Zpracovávám video, chvíli počkej...",
        "group_note": "\n🔗 Přidáno k existujícímu místu „{name}“.",
        "precision_note": "\n⚠️ Poloha je jen odhad (místo se nepodařilo najít na Google Maps).",
        "saved": "✅ Uloženo!\n📍 {name}\n🏷️ {category} | {tags}\n\n"
                 "{summary}\n🧭 {maps_url}{precision}{group_note}",

        # search command
        "search_none": "🔍 Pro „{query}“ jsem nic nenašel.",
        "search_header": "🔍 Nalezeno pro „{query}“:",
        "search_failed": "❌ Hledání selhalo: {error}",

        # Nearby places
        "nearby_none_saved": "Nemáš uložená žádná nenavštívená místa.",
        "nearby_nothing": "V okruhu {radius} km nemáš nic uloženo. Nejblíž je:\n"
                          "📍 {name} ({dist:.0f} km)\n🧭 {url}",
        "nearby_header": "📍 Nejbližší uložená místa ({count}):",

        # dedup command + merging
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
                        "Spusť {cmd} znovu.",
        "cb_merged": "Sloučeno",
        "merged_msg": "🔗 Sloučeno: „{a}“ + „{b}“ se teď na mapě zobrazí jako jedno místo.",
        "cb_error": "Chyba",
        "merge_failed": "❌ Sloučení selhalo: {error}",

        # Dedup (Claude verdicts)
        "dedup_reason_place_id": "Stejné místo podle Google Maps (place_id).",
        "dedup_reason_unparseable": "neparsovatelná odpověď: {raw}",
        # Instruction for Claude telling it which language to write the reason in
        # – inserted into the English prompt in dedup.py.
        "dedup_reason_lang": "in Czech",

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
        # {cmd} is filled in by the caller via command_name() from the BOT_COMMANDS registry
        "search_usage": "Usage: {cmd} <text>\ne.g. {cmd} waterslide",
        "dedup_started": "🔍 Checking for duplicate places, hang on...",
        # {commands} is filled in by help_text() from the BOT_COMMANDS registry
        "help": "📖 What I can do:\n\n"
                "🎬 Send me a video URL (Facebook/Instagram Reels, TikTok, "
                "YouTube Shorts) – I'll extract the place and save it to the sheet.\n"
                "📎 Send me your location and I'll find saved places nearby.\n\n"
                "Commands:\n{commands}",

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
                        "Run {cmd} again.",
        "cb_merged": "Merged",
        "merged_msg": "🔗 Merged: “{a}” + “{b}” will now show as one place on the map.",
        "cb_error": "Error",
        "merge_failed": "❌ Merge failed: {error}",

        "dedup_reason_place_id": "Same place according to Google Maps (place_id).",
        "dedup_reason_unparseable": "unparseable response: {raw}",
        "dedup_reason_lang": "in English",

        "export_doc_name": "Trips",
        "export_filename": "trips",
    },
}


# Bot command registry – the single place where a command is defined. It drives
# the dispatch in main.py (command_aliases), the Telegram menu (menu_commands)
# and the command list in the help text (help_text). Names in both languages
# always work as aliases, regardless of BOT_LANGUAGE.
BOT_COMMANDS = [
    {
        "key": "search",
        "name": {"cs": "hledej", "en": "search"},
        "extra_aliases": (),
        "arg": "<text>",
        "desc": {"cs": "Hledání v uložených místech",
                 "en": "Search your saved places"},
    },
    {
        "key": "dedup",
        "name": {"cs": "zkontroluj", "en": "dedup"},
        "extra_aliases": (),
        "arg": "",
        "desc": {"cs": "Kontrola duplicitních míst (návrhy na sloučení)",
                 "en": "Check for duplicate places (merge suggestions)"},
    },
    {
        "key": "id",
        "name": {"cs": "id", "en": "id"},
        "extra_aliases": (),
        "arg": "",
        "desc": {"cs": "Zobrazí tvoje Telegram user ID",
                 "en": "Show your Telegram user ID"},
    },
    {
        "key": "help",
        "name": {"cs": "help", "en": "help"},
        "extra_aliases": ("/start", "/napoveda"),
        "arg": "",
        "desc": {"cs": "Vypíše tuto nápovědu",
                 "en": "Show this help message"},
    },
]


def _command(key: str) -> dict:
    for cmd in BOT_COMMANDS:
        if cmd["key"] == key:
            return cmd
    raise KeyError(f"unknown bot command key: {key!r}")


def command_aliases(key: str) -> tuple[str, ...]:
    """All forms of a command for dispatch: "/name" in both languages + extra aliases."""
    cmd = _command(key)
    # dict.fromkeys: dedupes when the name is the same in both languages (e.g. /id)
    names = dict.fromkeys(f"/{cmd['name'][lang]}" for lang in SUPPORTED_LANGUAGES)
    return tuple(names) + tuple(cmd["extra_aliases"])


def command_name(key: str) -> str:
    """Command name with a slash in the bot's language (e.g. "/hledej") – for texts
    that refer to a command (search_usage, row_gone_msg)."""
    return f"/{_command(key)['name'][LANG]}"


def menu_commands() -> list[dict]:
    """Payload for Telegram setMyCommands in the bot's language."""
    return [{"command": cmd["name"][LANG], "description": cmd["desc"][LANG]}
            for cmd in BOT_COMMANDS]


def help_text() -> str:
    """The /help text – the command list is generated from BOT_COMMANDS so it
    cannot drift from the commands actually registered."""
    lines = []
    for cmd in BOT_COMMANDS:
        arg = f" {cmd['arg']}" if cmd["arg"] else ""
        lines.append(f"/{cmd['name'][LANG]}{arg} – {cmd['desc'][LANG]}")
    return t("help", commands="\n".join(lines))


def t(key: str, **kwargs) -> str:
    """Return the text in the bot's language; kwargs are substituted via str.format()."""
    text = MESSAGES[LANG][key]
    return text.format(**kwargs) if kwargs else text

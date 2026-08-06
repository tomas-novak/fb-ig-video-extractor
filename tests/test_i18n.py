"""Tests for the bot language (BOT_LANGUAGE) and configurable categories (CATEGORIES)."""
import pytest

from i18n import (BOT_COMMANDS, DEFAULT_CATEGORIES, MESSAGES, _parse_categories,
                  _parse_language, command_aliases, command_name, help_text,
                  menu_commands, t)


class TestParseLanguage:
    def test_empty_value_means_english(self):
        assert _parse_language("") == "en"
        assert _parse_language("  ") == "en"

    def test_supported_languages(self):
        assert _parse_language("cs") == "cs"
        assert _parse_language("en") == "en"
        assert _parse_language(" EN ") == "en"

    def test_unsupported_language_fails_at_startup(self):
        with pytest.raises(ValueError, match="BOT_LANGUAGE"):
            _parse_language("de")


class TestParseCategories:
    def test_empty_value_means_default_set_per_language(self):
        assert _parse_categories("", "cs") == DEFAULT_CATEGORIES["cs"]
        assert _parse_categories("", "en") == DEFAULT_CATEGORIES["en"]

    def test_custom_categories(self):
        assert _parse_categories("beach, food ,other", "en") == ["beach", "food", "other"]

    def test_duplicate_categories_fail_at_startup(self):
        with pytest.raises(ValueError, match="duplicate"):
            _parse_categories("beach,food,beach", "en")

    def test_default_set_is_not_shared_between_calls(self):
        cats = _parse_categories("", "cs")
        cats.append("x")
        assert "x" not in _parse_categories("", "cs")


class TestMessages:
    def test_both_languages_have_the_same_keys(self):
        assert MESSAGES["cs"].keys() == MESSAGES["en"].keys()

    def test_format_dedup_suggestion_handles_decimal_distance(self):
        # dedup_suggestion uses {distance:.1f} – it must receive a number
        for lang in ("cs", "en"):
            text = MESSAGES[lang]["dedup_suggestion"].format(
                a_name="A", a_date="2026-01-01", b_name="B", b_date="2026-01-02",
                distance=1.234, reason="test")
            assert "1.2" in text

    def test_t_returns_czech_text_in_tests(self):
        # conftest sets BOT_LANGUAGE=cs (the fixtures are Czech)
        assert "Uloženo" in t("saved", name="X", category="k", tags="t",
                              summary="s", maps_url="u", precision="", group_note="")

    def test_t_dosazuje_parametry(self):
        assert "42" in t("id_reply", user_id=42)


class TestBotCommands:
    def test_aliases_contain_both_languages(self):
        assert command_aliases("search") == ("/hledej", "/search")
        assert command_aliases("dedup") == ("/zkontroluj", "/dedup")

    def test_same_name_in_both_languages_is_not_duplicated(self):
        assert command_aliases("id") == ("/id",)

    def test_extra_help_aliases(self):
        aliases = command_aliases("help")
        assert "/help" in aliases and "/start" in aliases and "/napoveda" in aliases

    def test_unknown_key_raises(self):
        with pytest.raises(KeyError, match="unknown bot command"):
            command_aliases("does_not_exist")

    def test_menu_commands_czech(self):
        # conftest sets BOT_LANGUAGE=cs
        menu = menu_commands()
        assert {"command", "description"} == set(menu[0])
        assert [m["command"] for m in menu] == ["hledej", "zkontroluj", "id", "help"]

    def test_help_text_contains_all_commands_from_registry(self):
        text = help_text()
        assert "{commands}" not in text
        for cmd in BOT_COMMANDS:
            assert f"/{cmd['name']['cs']}" in text
        assert "/hledej <text>" in text

    def test_command_name_follows_language(self):
        # conftest sets BOT_LANGUAGE=cs
        assert command_name("search") == "/hledej"
        assert command_name("dedup") == "/zkontroluj"

    def test_messages_substitute_command_name_from_registry(self):
        assert "/hledej tobogán" in t("search_usage", cmd=command_name("search"))
        assert "Spusť /zkontroluj znovu" in t("row_gone_msg", cmd=command_name("dedup"))

    def test_help_text_english(self, monkeypatch):
        import i18n
        monkeypatch.setattr(i18n, "LANG", "en")
        text = help_text()
        assert "/search <text>" in text and "/dedup" in text
        assert [m["command"] for m in menu_commands()] == ["search", "dedup", "id", "help"]


class TestMapRender:
    def test_render_map_substitutes_language_and_categories(self):
        from map_page import render_map
        html = render_map()
        assert "__MAP_LANG__" not in html
        assert "__MAP_LANG_ATTR__" not in html
        assert "__MAP_CATEGORIES__" not in html
        assert '<html lang="cs">' in html
        assert '"koupání"' in html


class TestEnglishRuntime:
    """The English branch of the t() paths at runtime – conftest otherwise pins cs.

    Modules read the language via t() from the i18n.LANG global, so monkeypatching
    it is enough (map_page and analyzer import LANG into their own namespace, so
    they are patched separately)."""

    @pytest.fixture(autouse=True)
    def _english(self, monkeypatch):
        import i18n
        monkeypatch.setattr(i18n, "LANG", "en")

    def test_friendly_error_english(self):
        from main import friendly_error
        assert "photo" in friendly_error("ERROR: No video formats found!")
        assert "can't process" in friendly_error("Unsupported URL: https://x.com/...")
        msg = friendly_error("video is too long (12 min, limit 10 min)")
        assert msg.startswith("⏱️") and "short videos" in msg
        assert friendly_error("X" * 500).startswith("❌ Something went wrong")

    def test_duration_error_english(self):
        from extractor import duration_error
        assert "too long" in duration_error({"duration": 720})

    def test_bot_messages_english(self):
        assert "Your Telegram user ID: 42" in t("id_reply", user_id=42)
        assert "Saved!" in t("saved", name="X", category="food", tags="a",
                             summary="S", maps_url="U", precision="", group_note="")

    def test_render_map_english(self, monkeypatch):
        import map_page
        monkeypatch.setattr(map_page, "LANG", "en")
        html = map_page.render_map()
        assert '<html lang="en">' in html
        assert "__MAP_" not in html

    def test_system_prompt_english(self, monkeypatch):
        import analyzer
        monkeypatch.setattr(analyzer, "LANG", "en")
        sp = analyzer.system_prompt()
        assert sp.startswith("You are an AI assistant")
        assert "__" not in sp

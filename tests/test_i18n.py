"""Testy jazyka bota (BOT_LANGUAGE) a konfigurovatelných kategorií (CATEGORIES)."""
import pytest

from i18n import (BOT_COMMANDS, DEFAULT_CATEGORIES, MESSAGES, _parse_categories,
                  _parse_language, command_aliases, command_name, help_text,
                  menu_commands, t)


class TestParseLanguage:
    def test_prazdna_hodnota_znamena_anglictinu(self):
        assert _parse_language("") == "en"
        assert _parse_language("  ") == "en"

    def test_podporovane_jazyky(self):
        assert _parse_language("cs") == "cs"
        assert _parse_language("en") == "en"
        assert _parse_language(" EN ") == "en"

    def test_nepodporovany_jazyk_spadne_pri_startu(self):
        with pytest.raises(ValueError, match="BOT_LANGUAGE"):
            _parse_language("de")


class TestParseCategories:
    def test_prazdna_hodnota_znamena_vychozi_sadu_podle_jazyka(self):
        assert _parse_categories("", "cs") == DEFAULT_CATEGORIES["cs"]
        assert _parse_categories("", "en") == DEFAULT_CATEGORIES["en"]

    def test_vlastni_kategorie(self):
        assert _parse_categories("beach, food ,other", "en") == ["beach", "food", "other"]

    def test_duplicitni_kategorie_spadnou_pri_startu(self):
        with pytest.raises(ValueError, match="duplicate"):
            _parse_categories("beach,food,beach", "en")

    def test_vychozi_sada_se_nesdili_mezi_volanimi(self):
        cats = _parse_categories("", "cs")
        cats.append("x")
        assert "x" not in _parse_categories("", "cs")


class TestMessages:
    def test_oba_jazyky_maji_stejne_klice(self):
        assert MESSAGES["cs"].keys() == MESSAGES["en"].keys()

    def test_format_dedup_suggestion_zvlada_desetinnou_vzdalenost(self):
        # dedup_suggestion používá {distance:.1f} – musí dostat číslo
        for lang in ("cs", "en"):
            text = MESSAGES[lang]["dedup_suggestion"].format(
                a_name="A", a_date="2026-01-01", b_name="B", b_date="2026-01-02",
                distance=1.234, reason="test")
            assert "1.2" in text

    def test_t_vraci_cesky_text_v_testech(self):
        # conftest nastavuje BOT_LANGUAGE=cs (fixtures jsou české)
        assert "Uloženo" in t("saved", name="X", category="k", tags="t",
                              summary="s", maps_url="u", precision="", group_note="")

    def test_t_dosazuje_parametry(self):
        assert "42" in t("id_reply", user_id=42)


class TestBotCommands:
    def test_aliasy_obsahuji_oba_jazyky(self):
        assert command_aliases("search") == ("/hledej", "/search")
        assert command_aliases("dedup") == ("/zkontroluj", "/dedup")

    def test_stejny_nazev_v_obou_jazycich_se_neduplikuje(self):
        assert command_aliases("id") == ("/id",)

    def test_extra_aliasy_napovedy(self):
        aliases = command_aliases("help")
        assert "/help" in aliases and "/start" in aliases and "/napoveda" in aliases

    def test_neznamy_klic_spadne(self):
        with pytest.raises(KeyError, match="unknown bot command"):
            command_aliases("neexistuje")

    def test_menu_commands_cesky(self):
        # conftest nastavuje BOT_LANGUAGE=cs
        menu = menu_commands()
        assert {"command", "description"} == set(menu[0])
        assert [m["command"] for m in menu] == ["hledej", "zkontroluj", "id", "help"]

    def test_help_text_obsahuje_vsechny_prikazy_z_registru(self):
        text = help_text()
        assert "{commands}" not in text
        for cmd in BOT_COMMANDS:
            assert f"/{cmd['name']['cs']}" in text
        assert "/hledej <text>" in text

    def test_command_name_podle_jazyka(self):
        # conftest nastavuje BOT_LANGUAGE=cs
        assert command_name("search") == "/hledej"
        assert command_name("dedup") == "/zkontroluj"

    def test_zpravy_dosazuji_nazev_prikazu_z_registru(self):
        assert "/hledej tobogán" in t("search_usage", cmd=command_name("search"))
        assert "Spusť /zkontroluj znovu" in t("row_gone_msg", cmd=command_name("dedup"))

    def test_help_text_anglicky(self, monkeypatch):
        import i18n
        monkeypatch.setattr(i18n, "LANG", "en")
        text = help_text()
        assert "/search <text>" in text and "/dedup" in text
        assert [m["command"] for m in menu_commands()] == ["search", "dedup", "id", "help"]


class TestMapRender:
    def test_render_map_dosadi_jazyk_a_kategorie(self):
        from map_page import render_map
        html = render_map()
        assert "__MAP_LANG__" not in html
        assert "__MAP_LANG_ATTR__" not in html
        assert "__MAP_CATEGORIES__" not in html
        assert '<html lang="cs">' in html
        assert '"koupání"' in html


class TestEnglishRuntime:
    """Anglická větev t() cest za běhu – conftest jinak fixuje cs.

    Moduly čtou jazyk přes t() z globálu i18n.LANG, stačí ho tedy
    monkeypatchnout (map_page a analyzer si LANG importují do vlastního
    namespace, patchuje se jim zvlášť)."""

    @pytest.fixture(autouse=True)
    def _english(self, monkeypatch):
        import i18n
        monkeypatch.setattr(i18n, "LANG", "en")

    def test_friendly_error_anglicky(self):
        from main import friendly_error
        assert "photo" in friendly_error("ERROR: No video formats found!")
        assert "can't process" in friendly_error("Unsupported URL: https://x.com/...")
        msg = friendly_error("video is too long (12 min, limit 10 min)")
        assert msg.startswith("⏱️") and "short videos" in msg
        assert friendly_error("X" * 500).startswith("❌ Something went wrong")

    def test_duration_error_anglicky(self):
        from extractor import duration_error
        assert "too long" in duration_error({"duration": 720})

    def test_zpravy_bota_anglicky(self):
        assert "Your Telegram user ID: 42" in t("id_reply", user_id=42)
        assert "Saved!" in t("saved", name="X", category="food", tags="a",
                             summary="S", maps_url="U", precision="", group_note="")

    def test_render_map_anglicky(self, monkeypatch):
        import map_page
        monkeypatch.setattr(map_page, "LANG", "en")
        html = map_page.render_map()
        assert '<html lang="en">' in html
        assert "__MAP_" not in html

    def test_system_prompt_anglicky(self, monkeypatch):
        import analyzer
        monkeypatch.setattr(analyzer, "LANG", "en")
        sp = analyzer.system_prompt()
        assert sp.startswith("You are an AI assistant")
        assert "__" not in sp

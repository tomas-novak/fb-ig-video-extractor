"""Testy jazyka bota (BOT_LANGUAGE) a konfigurovatelných kategorií (CATEGORIES)."""
import pytest

from i18n import (DEFAULT_CATEGORIES, MESSAGES, _parse_categories,
                  _parse_language, t)


class TestParseLanguage:
    def test_prazdna_hodnota_znamena_cestinu(self):
        assert _parse_language("") == "cs"
        assert _parse_language("  ") == "cs"

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
        with pytest.raises(ValueError, match="duplicitní"):
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

    def test_t_vraci_cesky_text_ve_vychozim_nastaveni(self):
        # conftest nastavuje BOT_LANGUAGE="" -> cs
        assert "Uloženo" in t("saved", name="X", category="k", tags="t",
                              summary="s", maps_url="u", precision="", group_note="")

    def test_t_dosazuje_parametry(self):
        assert "42" in t("id_reply", user_id=42)


class TestMapRender:
    def test_render_map_dosadi_jazyk_a_kategorie(self):
        from map_page import render_map
        html = render_map()
        assert "__MAP_LANG__" not in html
        assert "__MAP_LANG_ATTR__" not in html
        assert "__MAP_CATEGORIES__" not in html
        assert '<html lang="cs">' in html
        assert '"koupání"' in html

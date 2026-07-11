"""Testy čistých funkcí z main.py: validace URL, příkazy, whitelist, tokeny."""
import pytest

import main
from main import (_parse_allowed_users, _token_matches, friendly_error,
                  is_command, is_valid_url)


class TestIsValidUrl:
    def test_https(self):
        assert is_valid_url("https://www.facebook.com/reel/123")

    def test_http(self):
        assert is_valid_url("http://example.com")

    def test_whitespace_around_url(self):
        assert is_valid_url("  https://www.instagram.com/reel/abc  ")

    def test_plain_text(self):
        assert not is_valid_url("ahoj bote")

    def test_empty(self):
        assert not is_valid_url("")

    def test_url_without_scheme(self):
        assert not is_valid_url("www.facebook.com/reel/123")


class TestIsCommand:
    def test_exact(self):
        assert is_command("/id", "/id")

    def test_with_bot_suffix(self):
        assert is_command("/id@MujBot", "/id")

    def test_with_argument(self):
        assert is_command("/hledej tobogán", "/hledej")

    def test_prefix_is_not_match(self):
        # '/idea' nesmí spustit '/id'
        assert not is_command("/idea", "/id")

    def test_case_insensitive(self):
        assert is_command("/ID", "/id")

    def test_empty_text(self):
        assert not is_command("", "/id")


class TestAllowedUsers:
    def test_empty_means_no_whitelist(self):
        assert _parse_allowed_users("") == set()

    def test_single_id(self):
        assert _parse_allowed_users("12345") == {12345}

    def test_multiple_ids_with_spaces(self):
        assert _parse_allowed_users("111, 222 ,333") == {111, 222, 333}

    def test_trailing_comma(self):
        assert _parse_allowed_users("111,") == {111}

    def test_username_fails_closed(self):
        # Překlep/@username = chyba konfigurace, ne tichý fallback na "všichni"
        with pytest.raises(ValueError):
            _parse_allowed_users("@pepa")

    def test_mixed_valid_invalid_fails(self):
        with pytest.raises(ValueError):
            _parse_allowed_users("111,abc")

    def test_is_authorized_with_whitelist(self, monkeypatch):
        monkeypatch.setattr(main, "ALLOWED_USERS", {42})
        assert main.is_authorized(42)
        assert not main.is_authorized(7)
        assert not main.is_authorized(None)

    def test_is_authorized_without_whitelist(self, monkeypatch):
        monkeypatch.setattr(main, "ALLOWED_USERS", set())
        assert main.is_authorized(7)
        assert main.is_authorized(None)


class TestTokenMatches:
    def test_match(self):
        assert _token_matches("tajny", "tajny")

    def test_mismatch(self):
        assert not _token_matches("spatny", "tajny")

    def test_empty_expected_never_matches(self):
        assert not _token_matches("", "")
        assert not _token_matches("cokoliv", "")

    def test_non_ascii_input_returns_false_instead_of_crash(self):
        # compare_digest se str argumenty vyžaduje ASCII – ne-ASCII nesmí shodit 500
        assert not _token_matches("žluťoučký", "tajny")


class TestFriendlyError:
    def test_photo_carousel(self):
        assert "fotka" in friendly_error("ERROR: No video formats found!")

    def test_login_required(self):
        assert "🔒" in friendly_error("Instagram: login required")

    def test_unsupported_url(self):
        assert "neumím zpracovat" in friendly_error("Unsupported URL: https://x.com/...")

    def test_unknown_error_is_truncated(self):
        msg = friendly_error("X" * 500)
        assert len(msg) < 300
        assert "❌" in msg

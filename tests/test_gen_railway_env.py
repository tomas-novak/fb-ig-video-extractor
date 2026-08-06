"""Tests for the Railway variables generator: quoting/escaping and service account checks."""
import io
import json

from dotenv import dotenv_values

from gen_railway_env import build_lines, format_env_line, parse_service_account

# A service account has a literal "\n" escape sequence inside private_key - the
# case most likely to break naive quoting, so the fixture keeps it realistic.
REAL_SA = {
    "type": "service_account",
    "project_id": "demo-1234",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg==\n-----END PRIVATE KEY-----\n",
    "client_email": "bot@demo-1234.iam.gserviceaccount.com",
}

# What .env.example ships - must never reach Railway.
PLACEHOLDER_SA = '{"type":"service_account","project_id":"..."}'


def roundtrip(key: str, value: str):
    """Emit the value, parse it back with dotenv, and return what came out."""
    line = format_env_line(key, value)
    return dotenv_values(stream=io.StringIO(line)).get(key)


class TestFormatEnvLine:
    def test_plain_value_stays_bare(self):
        assert format_env_line("TELEGRAM_BOT_TOKEN", "123456789:AAE_x-yZ") == \
            "TELEGRAM_BOT_TOKEN=123456789:AAE_x-yZ"

    def test_multiline_value_survives(self):
        value = "line one\nline two"
        assert roundtrip("INSTAGRAM_COOKIES", value) == value

    def test_multiline_with_double_quote_survives(self):
        # used to be dropped entirely: the naive wrapper produced unparseable output
        value = 'cookie "quoted" bit\nsecond line'
        assert roundtrip("INSTAGRAM_COOKIES", value) == value

    def test_hash_is_not_treated_as_comment(self):
        # used to be truncated at the "#"
        assert roundtrip("NOTE", "abc # not a comment") == "abc # not a comment"

    def test_edge_whitespace_is_preserved(self):
        # used to be trimmed
        assert roundtrip("PADDED", "  spaced  ") == "  spaced  "

    def test_backslashes_survive(self):
        assert roundtrip("COOKIES_FILE", r"C:\path\to\cookies.txt") == r"C:\path\to\cookies.txt"

    def test_single_quote_survives(self):
        assert roundtrip("NOTE", "it's fine") == "it's fine"

    def test_dollar_is_not_interpolated(self):
        assert roundtrip("NOTE", "a$bc") == "a$bc"

    def test_empty_value_is_quoted(self):
        assert format_env_line("EMPTY", "") == 'EMPTY=""'

    def test_service_account_json_reparses_after_roundtrip(self):
        compact = json.dumps(REAL_SA, ensure_ascii=False)
        got = roundtrip("GOOGLE_SERVICE_ACCOUNT_JSON", compact)
        assert json.loads(got) == REAL_SA

    def test_realistic_cookie_line_stays_bare(self):
        value = ".instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\tabc%3Adef"
        assert format_env_line("COOKIE", value) == f"COOKIE={value}"


class TestParseServiceAccount:
    def test_real_service_account_accepted(self):
        assert parse_service_account(json.dumps(REAL_SA)) == REAL_SA

    def test_env_example_placeholder_rejected(self):
        assert parse_service_account(PLACEHOLDER_SA) is None

    def test_missing_private_key_rejected(self):
        sa = {k: v for k, v in REAL_SA.items() if k != "private_key"}
        assert parse_service_account(json.dumps(sa)) is None

    def test_missing_client_email_rejected(self):
        sa = {k: v for k, v in REAL_SA.items() if k != "client_email"}
        assert parse_service_account(json.dumps(sa)) is None

    def test_empty_private_key_rejected(self):
        assert parse_service_account(json.dumps(REAL_SA | {"private_key": ""})) is None

    def test_malformed_json_rejected(self):
        assert parse_service_account("{not json") is None

    def test_non_object_rejected(self):
        assert parse_service_account('["a", "b"]') is None


class TestBuildLines:
    def _keys(self, lines):
        return [ln.split("=", 1)[0] for ln in lines]

    def test_skipped_keys_are_omitted(self):
        env = {"HOST": "127.0.0.1", "PORT": "8000", "PUBLIC_URL": "https://x",
               "FFMPEG_LOCATION": "/usr/bin/ffmpeg", "GOOGLE_SERVICE_ACCOUNT_FILE": "sa.json",
               "GEMINI_API_KEY": "key"}
        keys = self._keys(build_lines(env, "{}"))
        assert keys == ["GOOGLE_SERVICE_ACCOUNT_JSON", "GEMINI_API_KEY"]

    def test_empty_values_are_omitted(self):
        env = {"GEMINI_API_KEY": "key", "MAP_TOKEN": "", "CATEGORIES": ""}
        assert self._keys(build_lines(env, "{}")) == ["GOOGLE_SERVICE_ACCOUNT_JSON", "GEMINI_API_KEY"]

    def test_service_account_comes_from_argument_not_env(self):
        env = {"GOOGLE_SERVICE_ACCOUNT_JSON": PLACEHOLDER_SA}
        lines = build_lines(env, json.dumps(REAL_SA, ensure_ascii=False))
        assert self._keys(lines) == ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        parsed = dotenv_values(stream=io.StringIO("\n".join(lines)))
        assert json.loads(parsed["GOOGLE_SERVICE_ACCOUNT_JSON"]) == REAL_SA

    def test_cookies_file_is_kept(self):
        # local path, but extractor.py falls back to INSTAGRAM_COOKIES if it is invalid
        env = {"COOKIES_FILE": "cookies.txt"}
        assert "COOKIES_FILE" in self._keys(build_lines(env, "{}"))

    def test_whole_output_roundtrips(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "123:AAE",
            "INSTAGRAM_COOKIES": 'a "quoted" line\nsecond line',
            "NOTE": "value # with hash",
            "PADDED": "  spaced  ",
        }
        compact = json.dumps(REAL_SA, ensure_ascii=False)
        text = "\n".join(build_lines(env, compact)) + "\n"
        parsed = dotenv_values(stream=io.StringIO(text))
        for key, value in env.items():
            assert parsed[key] == value
        assert json.loads(parsed["GOOGLE_SERVICE_ACCOUNT_JSON"]) == REAL_SA

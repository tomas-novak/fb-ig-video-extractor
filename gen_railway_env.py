"""Helper script: generates railway-variables.local.txt for quick pasting into
Railway (dashboard -> Variables -> Raw Editor). That file is NOT committed
(it is in .gitignore).

It walks all the variables from the local .env automatically, so it does not go
stale when a new variable appears in .env.example. Exceptions:
- GOOGLE_SERVICE_ACCOUNT_FILE (a file path, for local development only) is
  converted to GOOGLE_SERVICE_ACCOUNT_JSON (the file contents on a single line).
  When that path does not exist, GOOGLE_SERVICE_ACCOUNT_JSON from .env is used
  instead (typically when .env was copied from the server). Either way the value
  has to look like a real service account - see parse_service_account().
- HOST, PORT, PUBLIC_URL and FFMPEG_LOCATION are skipped - they are either
  values specific to this particular machine (on Railway FFMPEG_LOCATION would
  point to a non-existent path and break ffmpeg, even though nixpacks.toml
  installs it), or Railway handles them itself (PORT, and it provides the domain
  via RAILWAY_PUBLIC_DOMAIN, which main.py uses automatically when PUBLIC_URL is
  not set). COOKIES_FILE is a local path too, but unlike FFMPEG_LOCATION it is
  not skipped - extractor.py._resolve_cookies() verifies it via os.path.exists()
  and falls back to INSTAGRAM_COOKIES without trouble, so an invalid local path
  breaks nothing.
- Values are quoted and escaped only when they need it (see format_env_line), so
  ordinary tokens stay plain while multi-line values such as INSTAGRAM_COOKIES
  survive the paste intact.

Fails closed: a missing .env or an unusable service account exits 1 without
writing anything, rather than producing a file that deploys and then fails
opaquely at runtime.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

# Values that must not travel to Railway - see the module docstring.
SKIP = {"HOST", "PORT", "PUBLIC_URL", "FFMPEG_LOCATION", "GOOGLE_SERVICE_ACCOUNT_FILE"}
OUTPUT_NAME = "railway-variables.local.txt"

# Characters that make a bare value ambiguous to a dotenv-style parser: quotes
# and backslashes need escaping, "#" would start a comment, newlines would split
# the entry, and "$"/"`" can be interpolated.
_QUOTE_TRIGGERS = ('"', "'", "#", "\n", "\r", "\\", "$", "`")


def format_env_line(key: str, value: str) -> str:
    """Render one KEY=VALUE line that parses back to exactly `value`.

    Bare when it is safe to be bare, so ordinary tokens stay readable. Otherwise
    double-quoted with `\\` and `"` escaped; newlines stay literal inside the
    quotes, which is the multi-line form both dotenv and Railway's Raw Editor
    accept. Leading/trailing whitespace forces quoting, since a bare value would
    be trimmed on the way back in.
    """
    if value and value == value.strip() and not any(c in value for c in _QUOTE_TRIGGERS):
        return f"{key}={value}"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}="{escaped}"'


def parse_service_account(raw: str) -> dict | None:
    """Return the parsed service account, or None when `raw` is not a usable one.

    Checked by shape rather than by matching the placeholder text, so this keeps
    working if .env.example's placeholder ever changes: a real service account is
    a JSON object carrying both a private_key and a client_email, neither of
    which the placeholder has.
    """
    try:
        sa = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(sa, dict) or not sa.get("private_key") or not sa.get("client_email"):
        return None
    return sa


def build_lines(env: dict, sa_compact: str) -> list[str]:
    """Build the output lines: the service account first, then everything else."""
    lines = [format_env_line("GOOGLE_SERVICE_ACCOUNT_JSON", sa_compact)]
    for key, value in env.items():
        if key in SKIP or key == "GOOGLE_SERVICE_ACCOUNT_JSON" or not value:
            continue
        lines.append(format_env_line(key, value))
    return lines


def resolve_service_account(env: dict) -> tuple[str | None, str | None]:
    """Pick the service account from the file path or from .env directly.

    Returns (compact_json, error). Re-serializing collapses a pretty-printed
    source onto one line, so both routes produce the same paste-ready value.
    """
    sa_file = env.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    sa_json = env.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if sa_file and os.path.exists(sa_file):
        with open(sa_file, encoding="utf-8") as f:
            raw = f.read()
        sa = parse_service_account(raw)
        if sa is None:
            return None, (f"GOOGLE_SERVICE_ACCOUNT_FILE={sa_file!r} is not a valid service "
                          "account (expected JSON with private_key and client_email).")
        return json.dumps(sa, ensure_ascii=False), None

    if sa_json:
        sa = parse_service_account(sa_json)
        if sa is None:
            hint = ""
            if sa_file:
                hint = (f" GOOGLE_SERVICE_ACCOUNT_FILE={sa_file!r} does not exist, so the value of "
                        "GOOGLE_SERVICE_ACCOUNT_JSON was used instead.")
            return None, ("GOOGLE_SERVICE_ACCOUNT_JSON does not hold a real service account - it "
                          "looks like the unfilled placeholder from .env.example (expected JSON "
                          f"with private_key and client_email).{hint}")
        return json.dumps(sa, ensure_ascii=False), None

    return None, ("Neither GOOGLE_SERVICE_ACCOUNT_FILE nor GOOGLE_SERVICE_ACCOUNT_JSON is "
                  "filled in in .env.")


def main() -> int:
    # Anchored to the script's own directory, not the cwd, so running it from
    # anywhere reads the same .env and writes the output next to it.
    base_dir = Path(__file__).resolve().parent
    env_path = base_dir / ".env"

    if not env_path.exists():
        print(f"ERROR: {env_path} does not exist - copy .env.example to .env and fill it in.",
              file=sys.stderr)
        return 1

    env = dotenv_values(env_path)
    if not env:
        print(f"ERROR: {env_path} contains no variables.", file=sys.stderr)
        return 1

    sa_compact, error = resolve_service_account(env)
    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    lines = build_lines(env, sa_compact)
    out_path = base_dir / OUTPUT_NAME
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Done: {out_path} ({len(lines)} variables)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

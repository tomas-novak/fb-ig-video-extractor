"""Helper script: generates railway-variables.local.txt for quick pasting into
Railway (dashboard -> Variables -> Raw Editor). That file is NOT committed
(it is in .gitignore).

It walks all the variables from the local .env automatically, so it does not go
stale when a new variable appears in .env.example. Exceptions:
- GOOGLE_SERVICE_ACCOUNT_FILE (a file path, for local development only) is
  converted to GOOGLE_SERVICE_ACCOUNT_JSON (the file contents on a single line).
  If the file at that path does not exist (e.g. an unchanged placeholder from
  .env.example), or GOOGLE_SERVICE_ACCOUNT_JSON is already filled in directly in
  .env (typically when .env was copied from the server), that value is used.
- HOST, PORT, PUBLIC_URL and FFMPEG_LOCATION are skipped - they are either
  values specific to this particular machine (on Railway FFMPEG_LOCATION would
  point to a non-existent path and break ffmpeg, even though nixpacks.toml
  installs it), or Railway handles them itself (PORT, and it provides the domain
  via RAILWAY_PUBLIC_DOMAIN, which main.py uses automatically when PUBLIC_URL is
  not set). COOKIES_FILE is a local path too, but unlike FFMPEG_LOCATION it is
  not skipped - extractor.py._resolve_cookies() verifies it via os.path.exists()
  and falls back to INSTAGRAM_COOKIES without trouble, so an invalid local path
  breaks nothing.
- Multi-line values (typically INSTAGRAM_COOKIES) are written in quotes so they
  do not fall apart into separate lines when pasted into Railway.
"""
import json
import os
import sys
from dotenv import dotenv_values

env = dotenv_values(".env")
skip = {"HOST", "PORT", "PUBLIC_URL", "FFMPEG_LOCATION", "GOOGLE_SERVICE_ACCOUNT_FILE"}
lines = []

sa_file = env.get("GOOGLE_SERVICE_ACCOUNT_FILE")
sa_json = env.get("GOOGLE_SERVICE_ACCOUNT_JSON")

# Always warn, regardless of whether GOOGLE_SERVICE_ACCOUNT_JSON contains
# anything - .env.example ships both variables already filled with placeholders,
# so "sa_json has a value" alone does not mean it is the real content.
if sa_file and not os.path.exists(sa_file):
    print(
        f"WARNING: GOOGLE_SERVICE_ACCOUNT_FILE={sa_file!r} does not exist - check "
        "that GOOGLE_SERVICE_ACCOUNT_JSON below holds the real service account "
        "content, not the unfilled placeholder from .env.example.",
        file=sys.stderr,
    )

if sa_file and os.path.exists(sa_file):
    sa = json.load(open(sa_file, encoding="utf-8"))
    lines.append(f"GOOGLE_SERVICE_ACCOUNT_JSON={json.dumps(sa, ensure_ascii=False)}")
elif sa_json:
    lines.append(f"GOOGLE_SERVICE_ACCOUNT_JSON={sa_json}")
else:
    print(
        "WARNING: neither GOOGLE_SERVICE_ACCOUNT_FILE nor "
        "GOOGLE_SERVICE_ACCOUNT_JSON is filled in in .env.",
        file=sys.stderr,
    )

for key, value in env.items():
    if key in skip or key == "GOOGLE_SERVICE_ACCOUNT_JSON" or not value:
        continue
    if "\n" in value:
        value = f'"{value}"'
    lines.append(f"{key}={value}")

with open("railway-variables.local.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Done: railway-variables.local.txt ({len(lines)} variables)")

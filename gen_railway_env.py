"""Pomocný skript: vygeneruje railway-variables.local.txt pro vložení do Railway.
Tento soubor se NEcommituje (je v .gitignore). Smazat lze po nasazení."""
import json
from dotenv import dotenv_values

env = dotenv_values(".env")
sa = json.load(open(env["GOOGLE_SERVICE_ACCOUNT_FILE"], encoding="utf-8"))
sa_line = json.dumps(sa, ensure_ascii=False)

lines = [
    f"TELEGRAM_BOT_TOKEN={env['TELEGRAM_BOT_TOKEN']}",
    f"GEMINI_API_KEY={env['GEMINI_API_KEY']}",
    f"GOOGLE_SHEETS_ID={env['GOOGLE_SHEETS_ID']}",
    f"GOOGLE_SERVICE_ACCOUNT_JSON={sa_line}",
    "WEBHOOK_SECRET=vylety_secret_2026",
]

with open("railway-variables.local.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Hotovo: railway-variables.local.txt ({len(lines)} promennych)")

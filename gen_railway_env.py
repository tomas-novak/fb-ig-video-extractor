"""Pomocný skript: vygeneruje railway-variables.local.txt pro rychlé vložení
do Railway (dashboard -> Variables -> Raw Editor). Tento soubor se
NEcommituje (je v .gitignore).

Projde všechny proměnné z lokálního .env automaticky, takže nezastarává,
když se v .env.example objeví nová proměnná. Výjimky:
- GOOGLE_SERVICE_ACCOUNT_FILE (cesta k souboru, jen pro lokální vývoj) se
  převede na GOOGLE_SERVICE_ACCOUNT_JSON (obsah souboru na jeden řádek),
  což je varianta, kterou aplikace čte na serveru.
- HOST, PORT a PUBLIC_URL se přeskakují - Railway PORT nastavuje samo a
  veřejnou adresu poskytuje přes RAILWAY_PUBLIC_DOMAIN, které main.py
  používá automaticky, pokud PUBLIC_URL není nastavené.
"""
import json
from dotenv import dotenv_values

env = dotenv_values(".env")
skip = {"HOST", "PORT", "PUBLIC_URL", "GOOGLE_SERVICE_ACCOUNT_FILE", "GOOGLE_SERVICE_ACCOUNT_JSON"}
lines = []

sa_file = env.get("GOOGLE_SERVICE_ACCOUNT_FILE")
if sa_file:
    sa = json.load(open(sa_file, encoding="utf-8"))
    lines.append(f"GOOGLE_SERVICE_ACCOUNT_JSON={json.dumps(sa, ensure_ascii=False)}")

for key, value in env.items():
    if key in skip or not value:
        continue
    lines.append(f"{key}={value}")

with open("railway-variables.local.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Hotovo: railway-variables.local.txt ({len(lines)} promennych)")

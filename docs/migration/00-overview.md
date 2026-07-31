# Migrace z Railway — přehled

Tenhle adresář popisuje odchod z Railway (končí předplatné) na vlastní VPS,
rozdělený do dvou fází.

| Soubor | Co obsahuje |
|---|---|
| `00-overview.md` | tenhle přehled, stav serveru, rozhodnutí a checklist |
| `01-phase-a-vps.md` | **runbook** — přesun bota na VPS krok za krokem |
| `02-phase-b-supabase-vercel.md` | návrh druhé fáze (Supabase + mapa na Vercelu) |
| `03-rollback.md` | jak se vrátit zpět, kdyby něco nefungovalo |

---

## Co musí zůstat zachované

- komunikace přes Telegram (webhook, stejný bot, stejné příkazy),
- zpracování videí (yt-dlp → Gemini → zápis),
- mapa s místy.

Zbytek infrastruktury je otevřený.

## Co aplikace potřebuje od hostingu

Tohle rozhodlo o výběru řešení víc než cokoliv jiného:

1. **Dlouhoběžící proces.** Webhook odpoví Telegramu okamžitě a video se pak
   zpracovává na pozadí 30 sekund až ~3 minuty (`main.py`, `_background_tasks`).
   Tím padá klasický serverless (Vercel funkce, Lambda) — funkce by skončila
   dřív než práce.
2. **ffmpeg** kvůli yt-dlp.
3. **Zapisovatelný disk** — videa se stahují do dočasného adresáře, u delších
   klidně stovky MB.
4. **Stabilní veřejná HTTPS adresa** pro Telegram webhook.
5. **Jedna instance.** Zápisy do Google Sheets nejsou odolné vůči souběhu,
   takže se neškáluje do šířky.

Naopak nic trvalého na serveru neleží — všechna data jsou v Google Sheets.
To dělá celý přesun podstatně jednodušší: nemigrují se žádná data.

## Stav VPS (zjištěno před migrací)

| Položka | Hodnota |
|---|---|
| OS | Ubuntu 22.04 LTS, x86_64 |
| CPU | 3 jádra |
| RAM | 3,8 GiB (~1,2 GiB dostupné), swap 4 GiB |
| Disk | 22 GiB volných, `/tmp` na disku (ne v RAM) |
| Docker | **není nainstalovaný** |
| ffmpeg | **4.4.2, už nainstalovaný** |
| Porty 80 / 443 / 8000 | volné |
| Reverse proxy | žádná |
| Firewall | na serveru žádný (ufw/iptables chybí) |
| Ostatní služby | Hermes (~425 MiB RAM), dashboard na 8765, lokální PostgreSQL |

Dvě věci z toho plynou přímo:

- **ffmpeg už je** a **Docker není** → nasazení nativně přes systemd + venv je
  méně práce i méně paměti (Docker daemon by ukrojil dalších ~150–200 MiB).
- **RAM je těsná** → bot musí mít limity, aby při nedostatku paměti systém
  nikdy nesáhl na Hermes. Řešeno v `deploy/fbig-bot.service`, vysvětleno
  v `01-phase-a-vps.md`.

## Zvažované varianty

| Varianta | Proč (ne)zvolena |
|---|---|
| **VPS + systemd + Caddy** ✅ | nejnižší režie, ffmpeg už je, plná kontrola, nulové náklady navíc |
| VPS + Docker | funguje (v repu je `Dockerfile` i `docker-compose.yml`), ale na 3,8 GiB serveru je režie daemonu zbytečná |
| Vercel / serverless | **nejde** — background tasky běží minuty, funkce by je nedoběhla; potřebovalo by to frontu a stejně někde workera |
| Jiný PaaS (Fly.io, Render…) | funguje, ale je to jen odložení stejného problému na jiný účet a jiný free tier |

## Fáze

### Fáze A — pryč z Railway (`01-phase-a-vps.md`)
Bot se přesune na VPS beze změny architektury. Google Sheets i mapa zůstávají,
jak jsou. Cíl: co nejrychleji a nejbezpečněji opustit Railway.

### Fáze B — Supabase + mapa na Vercelu (`02-phase-b-supabase-vercel.md`)
Až bude Fáze A ověřeně stabilní. Data ze Sheets do Postgresu (rychlejší
dotazy, skutečné ID místo čísel řádků), mapa jako samostatná aplikace.
Fáze B je volitelná — po Fázi A je systém plně funkční.

---

## Checklist

### Fáze A
- [ ] Založená DuckDNS subdoména, A záznam míří na server
- [ ] Nainstalované závislosti (Python venv, Caddy)
- [ ] Aplikace naklonovaná v `/opt/fbig-bot`, venv hotový
- [ ] `.env` vyplněný (hodnoty přenesené z Railway) včetně `PUBLIC_URL` a `HOST`
- [ ] Služba `fbig-bot` běží, limity paměti platí
- [ ] Caddy běží, certifikát vydaný, `/health` odpovídá přes HTTPS
- [ ] Webhook přeregistrovaný na novou adresu
- [ ] Otestované: `/id`, reálné video, `/hledej`, `/zkontroluj`, mapa
- [ ] Vyzkoušený rollback (webhook zpět na Railway a zase na VPS)
- [ ] Po několika dnech provozu: **smazaná služba na Railway**

### Fáze B (později)
- [ ] Založený Supabase projekt a schéma
- [ ] Data přenesená ze Sheets, počty sedí
- [ ] Bot přepnutý na Supabase, testy zelené
- [ ] Mapa nasazená na Vercelu

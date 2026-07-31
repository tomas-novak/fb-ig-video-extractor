# Fáze A — přesun bota na VPS

Runbook krok za krokem. Výsledek: bot běží na vlastním serveru jako systemd
služba, HTTPS zajišťuje Caddy, Railway se dá vypnout.

**Odhadovaný čas:** 30–45 minut.

**Důležité:** Railway během celé fáze necháváme běžet. Přepnutí na nový server
je jediné volání Telegram API (krok 8) a stejně rychle se dá vzít zpět —
viz [`03-rollback.md`](03-rollback.md).

Příkazy níže předpokládají přihlášení na server jako root (jinak `sudo`).

---

## 1. DuckDNS — veřejná adresa zdarma

Telegram doručuje webhooky jen na HTTPS s platným certifikátem, takže samotná
IP adresa nestačí. Pokud vlastní doménu nemáš, DuckDNS ji dá zdarma.

1. Otevři [duckdns.org](https://www.duckdns.org), přihlas se (GitHub/Google).
2. Do pole „domains" napiš název, např. `mujbot`, a dej **add domain**.
   Vznikne `mujbot.duckdns.org`.
3. Do pole `current ip` vyplň veřejnou IP svého serveru a ulož.
   Zjistíš ji na serveru příkazem `curl -s ifconfig.me`.
4. Nahoře na stránce si zkopíruj **token** — bude potřeba v kroku 7.

Ověření (na serveru), že DNS už platí:

```bash
dig +short mujbot.duckdns.org
# musí vypsat IP tvého serveru
```

DNS se občas propisuje pár minut. Než odpoví správně, nemá smysl pokračovat
ke kroku 6 — Let's Encrypt by certifikát nevydal.

---

## 2. Balíčky

```bash
apt update
apt install -y python3-venv python3-pip git curl
```

Ubuntu 22.04 má Python 3.10 a ten aplikaci stačí (ověřeno — kód nepoužívá
žádnou konstrukci vyžadující 3.11). `ffmpeg` už je na serveru nainstalovaný,
netřeba ho řešit.

Caddy z oficiálního repozitáře:

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install -y caddy
```

---

## 3. Uživatel a aplikace

Bot poběží pod vlastním uživatelem bez práv navíc:

```bash
# Bez --create-home: adresář musí zůstat neexistující, aby do něj šlo klonovat.
useradd --system --home-dir /opt/fbig-bot --shell /usr/sbin/nologin fbigbot

git clone https://github.com/tomas-novak/fb-ig-video-extractor.git /opt/fbig-bot
chown -R fbigbot:fbigbot /opt/fbig-bot
```

Virtuální prostředí a závislosti:

```bash
sudo -u fbigbot python3 -m venv /opt/fbig-bot/venv
sudo -u fbigbot /opt/fbig-bot/venv/bin/pip install --upgrade pip
sudo -u fbigbot /opt/fbig-bot/venv/bin/pip install -r /opt/fbig-bot/requirements.txt
```

---

## 4. Konfigurace `.env`

```bash
sudo -u fbigbot cp /opt/fbig-bot/.env.example /opt/fbig-bot/.env
sudo -u fbigbot nano /opt/fbig-bot/.env
chmod 600 /opt/fbig-bot/.env
```

Hodnoty se přenášejí z Railway dashboardu (Variables). **Zatím nech
`PUBLIC_URL` prázdné** — díky tomu se bot nepokusí převzít webhook a Railway
zůstane netknuté, dokud si nasazení neověříš.

| Proměnná | Odkud vzít | Povinná |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | z Railway (stejný bot) | ano |
| `GEMINI_API_KEY` | z Railway | ano |
| `GOOGLE_SHEETS_ID` | z Railway | ano |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | z Railway (celý JSON na jednom řádku) | ano |
| `GOOGLE_MAPS_API_KEY` | z Railway (Places API) | pro přesné souřadnice |
| `ANTHROPIC_API_KEY` | z Railway | pro `/zkontroluj` |
| `TELEGRAM_ALLOWED_USERS` | z Railway | doporučeno |
| `MAP_TOKEN`, `MAP_VIEW_TOKEN` | z Railway | doporučeno |
| `WEBHOOK_SECRET` | z Railway | volitelné |
| `BOT_LANGUAGE`, `CATEGORIES`, `MAX_VIDEO_MINUTES` | z Railway | volitelné |
| `COOKIES_FILE` | viz poznámka níže | pro Instagram/YouTube |
| **`PUBLIC_URL`** | zatím **nechat prázdné**, vyplní se v kroku 8 | ano (později) |
| **`HOST`** | `127.0.0.1` | ano |
| `PORT` | `8000` (nebo nechat prázdné) | ne |

`HOST=127.0.0.1` je tady důležitý: server nemá firewall, takže bez něj by byl
port 8000 dostupný z internetu i mimo Caddy.

**Cookies:** na Railway se používala proměnná `INSTAGRAM_COOKIES` s celým
obsahem souboru. Na VPS je jednodušší soubor — nahraj `cookies.txt` do
`/opt/fbig-bot/cookies.txt` a nastav `COOKIES_FILE=/opt/fbig-bot/cookies.txt`.
Musí ležet uvnitř `/opt/fbig-bot`, protože služba má zakázaný přístup do
domovských adresářů.

```bash
chown fbigbot:fbigbot /opt/fbig-bot/cookies.txt
chmod 600 /opt/fbig-bot/cookies.txt
```

---

## 5. systemd služba

```bash
cp /opt/fbig-bot/deploy/fbig-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now fbig-bot
systemctl status fbig-bot
```

Bot teď běží na `127.0.0.1:8000`, ale webhook má pořád Railway (`PUBLIC_URL`
je prázdné). Rychlá kontrola:

```bash
curl -s localhost:8000/health
```

### Jak jsou chráněné ostatní služby na serveru

Unit obsahuje tři nezávislé vrstvy, aby při nedostatku paměti systém sáhl
**vždy na bota a nikdy na Hermes**:

1. **`MemoryMax=800M`** — bot má vlastní cgroup a narazí na svůj strop dřív,
   než dojde paměť celého serveru. Kill proběhne uvnitř té cgroup, takže se
   globální OOM killer vůbec nespustí. `MemorySwapMax=512M` navíc brání tomu,
   aby zaplnil swap a rozthrashoval disk.
2. **`OOMScoreAdjust=1000`** — pojistka pro případ, že by paměť došla vinou
   něčeho jiného. Je to maximum stupnice (−1000 až 1000) a znamená „mě zabij
   první". Hodnotu dědí i `yt-dlp` a `ffmpeg` spuštěné během stahování.
3. **`Nice=10`, `CPUWeight=50`, `IOWeight=50`** — stahování videa nezpomalí
   ostatní služby.

Když bota kernel opravdu zabije, systemd ho do pěti sekund nastartuje zpátky
(`Restart=always`). Ztratí se jen rozpracované video — stačí poslat URL znovu.

Ověření, že limity platí:

```bash
systemctl show fbig-bot -p MemoryMax -p MemorySwapMax -p OOMScoreAdjust
systemd-cgtop      # živá spotřeba, ukončí se klávesou q
```

Volitelně se dá Hermes chránit i z druhé strany — snížením jeho OOM skóre:

```bash
choom -n -500 -p "$(pgrep -f 'hermes gateway')"
```

Platí jen do restartu procesu. Trvale by to řešil řádek
`OOMScoreAdjust=-500` v `hermes-gateway.service` (ta unit na serveru existuje,
ale je vypnutá — Hermes běží jako samostatný proces).

---

## 6. Caddy a HTTPS

```bash
cp /opt/fbig-bot/deploy/Caddyfile /etc/caddy/Caddyfile
nano /etc/caddy/Caddyfile     # doplnit svou doménu a e-mail
systemctl reload caddy
```

Caddy si sám vyžádá certifikát od Let's Encrypt. První pokus trvá pár sekund:

```bash
systemctl status caddy
curl -s https://mujbot.duckdns.org/health
```

Když `/health` odpoví přes HTTPS, je hotová ta podstatná část.

---

## 7. DuckDNS — pravidelná obnova

DuckDNS nechává neaktivní domény vypršet. Cron to jednou za pět minut potvrdí:

Skript se spouští rovnou z `deploy/`, aby ho `update.sh` (git pull) udržoval
aktuální — kopie jinam by zůstala navždy taková, jaká byla při instalaci.

```bash
cat > /etc/duckdns.conf <<'EOF'
DUCKDNS_DOMAIN=mujbot
DUCKDNS_TOKEN=sem-vloz-token-z-duckdns
EOF
chmod 600 /etc/duckdns.conf

/opt/fbig-bot/deploy/duckdns-refresh.sh      # musí vypsat "DuckDNS OK: ..."

crontab -e
# přidat řádek:
# */5 * * * * /opt/fbig-bot/deploy/duckdns-refresh.sh >/dev/null 2>&1
```

---

## 8. Přepnutí webhooku na VPS

Tohle je jediný okamžik, kdy se provoz skutečně přesune. Telegram doručuje
zprávy vždy jen na **naposledy zaregistrovanou** adresu, takže Railway tím
automaticky přestane dostávat zprávy (běžet ale může dál jako záloha).

```bash
sudo -u fbigbot nano /opt/fbig-bot/.env
# PUBLIC_URL=https://mujbot.duckdns.org

systemctl restart fbig-bot
journalctl -u fbig-bot -n 20 --no-pager
```

V logu musí být řádek `[webhook] setWebhook https://mujbot.duckdns.org/webhook -> ...`.

Kontrola u Telegramu:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Očekává se nová URL, `pending_update_count` blízko nule a prázdné
`last_error_message`.

---

## 9. Ověření

- [ ] `systemctl status fbig-bot caddy` — obě služby `active (running)`
- [ ] `curl -s https://mujbot.duckdns.org/health` — odpoví
- [ ] `ss -tlnp | grep 8000` — poslouchá jen na `127.0.0.1`
- [ ] `systemctl show fbig-bot -p MemoryMax -p OOMScoreAdjust` — limity platí
- [ ] Telegram: `/id` odpoví
- [ ] Telegram: pošli reálný odkaz na Reel → přijde odpověď a v Google Sheets
      přibude řádek
- [ ] Telegram: `/help`, `/hledej praha`, `/zkontroluj`
- [ ] Mapa: `https://mujbot.duckdns.org/map?token=<MAP_TOKEN>` ukazuje piny
- [ ] **Zkouška návratu**: podle [`03-rollback.md`](03-rollback.md) přepni
      webhook zpět na Railway, ověř, že bot odpovídá, a přepni zase na VPS

Až tohle všechno projde a server pojede pár dní bez problémů, teprve pak
smaž službu na Railway.

---

## 10. Provoz

**Logy:**

```bash
journalctl -u fbig-bot -f          # živě
journalctl -u fbig-bot -n 100      # posledních 100 řádků
journalctl -u fbig-bot --since "1 hour ago"
```

**Restart:**

```bash
systemctl restart fbig-bot
```

**Aktualizace** (náhrada automatického deploye z Railway):

```bash
/opt/fbig-bot/deploy/update.sh
```

Skript stáhne kód, doinstaluje závislosti, **aktualizuje yt-dlp** a restartuje
službu. yt-dlp je dobré aktualizovat pravidelně — sociální sítě mění formáty
a stará verze prostě přestane stahovat.

**Spotřeba:**

```bash
systemctl status fbig-bot | grep Memory
systemd-cgtop
```

---

## 11. Troubleshooting

**Služba nenaběhne hned po startu.**
Nejčastěji chybí nebo je špatně proměnná v `.env` — aplikace v takovém případě
spadne už při importu. `journalctl -u fbig-bot -n 50` ukáže konkrétní chybu
(`KeyError: 'TELEGRAM_BOT_TOKEN'`, `ValueError: TELEGRAM_ALLOWED_USERS ...`).

**Caddy nevydá certifikát.**
Zkontroluj, že `dig +short mujbot.duckdns.org` vrací IP serveru a že na porty
80 a 443 nic jiného neposlouchá (`ss -tlnp | grep -E ':80|:443'`). Let's Encrypt
potřebuje port 80 dostupný zvenku.

**Caddy vrací 502.**
Bot neběží nebo poslouchá jinde. `systemctl status fbig-bot` a
`ss -tlnp | grep 8000`. Musí sedět `HOST`/`PORT` v `.env` s adresou
v `reverse_proxy` v Caddyfile.

**Bot neodpovídá v Telegramu, ale `/health` funguje.**
Webhook míří jinam. `getWebhookInfo` (krok 8) ukáže aktuální URL a případnou
chybu doručení. Nezapomeň, že registrovaný může být vždy jen jeden.

**Bot je opakovaně zabíjen kvůli paměti.**
V logu se objeví `oom` nebo `Killed`. Zkontroluj `systemd-cgtop`; když bot
běžně naráží na 800 MB, zvedni `MemoryMax` v
`/etc/systemd/system/fbig-bot.service` (server má 4 GiB swap jako polštář)
a dej `systemctl daemon-reload && systemctl restart fbig-bot`. Případně sniž
`MAX_VIDEO_MINUTES` — dlouhá videa jsou největší žrout.

**Přestalo fungovat stahování z Instagramu / YouTube.**
Nejdřív `/opt/fbig-bot/deploy/update.sh` (aktualizuje yt-dlp). Když to
nepomůže, budou potřeba čerstvé cookies — ze serverové IP je obě sítě
vyžadují častěji. Diagnostika: `https://mujbot.duckdns.org/debug?token=<MAP_TOKEN>`.

---

## 12. Poznámka mimo rozsah migrace

Bot sám je po dokončení návodu schovaný za Caddy (`HOST=127.0.0.1`), ale
ostatní služby na serveru tak nastavené být nemusí. Vyplatí se projít, co
je z internetu dostupné:

```bash
ss -tlnp | grep -v '127.0.0.1\|::1'
```

Co nemá být veřejné, patří buď za `127.0.0.1`, nebo za firewall
u poskytovatele — server sám žádný nastavený nemá.

# Deploying on your own VPS

Step-by-step guide to running your own instance as a systemd service behind
Caddy, with free HTTPS. Works on any small Linux VPS (DigitalOcean, Hetzner,
a $5/mo box, a spare machine at home with a public IP — anything).

**Estimated time:** 30–45 minutes.

Not sure yet whether this project is for you? [Try the live map demo](https://tomas-novak.github.io/fb-ig-video-extractor/) first (static sample data, no deployment needed).

Commands below assume you're logged in as root (otherwise prefix with `sudo`).

## Why this shape

The bot needs a **long-lived process** — a Telegram webhook returns
immediately and the video is then processed as a background task for up to a
few minutes. That rules out request-scoped serverless (Vercel functions,
Lambda): the function would time out before the work finishes.

It also needs:
- **ffmpeg** (used by yt-dlp)
- a **writable temp directory** — videos are downloaded there, sometimes
  hundreds of MB for longer ones
- a **stable public HTTPS address** for the Telegram webhook
- to run as a **single instance** — writes to Google Sheets aren't
  concurrency-safe, so this doesn't scale horizontally

Nothing persistent lives on the server itself — all data is in Google
Sheets — so there's no state to worry about beyond the `.env` file and an
optional cookies file.

**VPS + systemd + Caddy** (this guide) needs the least resources: no
container runtime overhead, and most VPS images already ship without
Docker. If you'd rather use Docker (VPS, NAS, Raspberry Pi), the repo also
ships a `Dockerfile` and `docker-compose.yml` — see the main
[README](../README.md) for that path instead.

---

## 1. DuckDNS — a free public domain

Telegram only delivers webhooks over HTTPS with a valid certificate, so a
bare IP address isn't enough. If you don't already own a domain, DuckDNS
gives you one for free.

1. Open [duckdns.org](https://www.duckdns.org) and sign in (GitHub/Google).
2. Under "domains", type a name, e.g. `mybot`, and hit **add domain**. This
   creates `mybot.duckdns.org`.
3. Fill in `current ip` with your server's public IP and save. Find it on
   the server with `curl -s ifconfig.me`.
4. Copy the **token** shown at the top of the page — you'll need it in
   step 7.

Verify (on the server) that DNS has propagated before continuing:

```bash
dig +short mybot.duckdns.org
# must print your server's IP
```

If it prints a different IP (or none), fix the `current ip` field on
duckdns.org and wait a few minutes before moving on — Let's Encrypt won't
issue a certificate until this matches.

---

## 2. Packages

```bash
apt update
apt install -y python3-venv python3-pip git curl ffmpeg
```

Ubuntu 22.04 ships Python 3.10, which is enough (nothing in the code
requires 3.11+).

Caddy from the official repository:

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

## 3. User and application

The bot runs under its own unprivileged user:

```bash
# No --create-home: the directory must not exist yet, so git clone can create it.
useradd --system --home-dir /opt/fbig-bot --shell /usr/sbin/nologin fbigbot

git clone https://github.com/tomas-novak/fb-ig-video-extractor.git /opt/fbig-bot
chown -R fbigbot:fbigbot /opt/fbig-bot
```

Virtualenv and dependencies:

```bash
sudo -u fbigbot python3 -m venv /opt/fbig-bot/venv
sudo -u fbigbot /opt/fbig-bot/venv/bin/pip install --upgrade pip
sudo -u fbigbot /opt/fbig-bot/venv/bin/pip install -r /opt/fbig-bot/requirements.txt
```

---

## 4. `.env` configuration

```bash
sudo -u fbigbot cp /opt/fbig-bot/.env.example /opt/fbig-bot/.env
chmod 600 /opt/fbig-bot/.env
sudo -u fbigbot nano /opt/fbig-bot/.env
```

See the main [README](../README.md#setup--your-own-instance-15-minutes-all-free)
for how to obtain each key (Telegram bot token, Gemini key, Google Sheets +
service account, etc.). A few values specific to this deployment method:

| Variable | Value | Required |
|---|---|---|
| **`HOST`** | `127.0.0.1` | yes |
| `PORT` | `8000` (or leave blank) | no |
| **`PUBLIC_URL`** | leave **blank** for now — filled in during step 8, once HTTPS works | yes (later) |
| `COOKIES_FILE` | see note below | for Instagram/YouTube |

`HOST=127.0.0.1` matters: if your server has no firewall configured, without
it port 8000 would be reachable directly from the internet, bypassing Caddy.

Leaving `PUBLIC_URL` blank for now matters too: the bot registers its
Telegram webhook on every startup when it's set, and HTTPS doesn't exist
until step 6 — registering early would just queue up failed deliveries.

**Cookies:** Instagram and YouTube usually block anonymous downloads from
datacenter IPs. Export cookies from a logged-in account (an extension like
*Get cookies.txt LOCALLY*) and upload the file to
`/opt/fbig-bot/cookies.txt`, then set `COOKIES_FILE=/opt/fbig-bot/cookies.txt`.
It must live inside `/opt/fbig-bot` — the service has no access to home
directories.

```bash
chown fbigbot:fbigbot /opt/fbig-bot/cookies.txt
chmod 600 /opt/fbig-bot/cookies.txt
```

---

## 5. systemd service

```bash
cp /opt/fbig-bot/deploy/fbig-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now fbig-bot
systemctl status fbig-bot
```

Quick check:

```bash
curl -s localhost:8000/health
```

### About the memory/OOM protection in the unit file

If your server also runs other important long-lived processes, a runaway
video download shouldn't be able to take them down. The unit has three
independent layers so the kernel always picks the bot first when memory
runs short:

1. **`MemoryMax=800M`** — the bot has its own cgroup and hits its own
   ceiling before the whole server runs out of memory. The kill happens
   inside that cgroup, so the global OOM killer never has to get involved.
   `MemorySwapMax=512M` additionally stops it from filling swap and
   thrashing the disk.
2. **`OOMScoreAdjust=1000`** — a safety net in case memory runs out for any
   other reason. This is the maximum on the scale (−1000 to 1000) and means
   "kill me first." `yt-dlp` and `ffmpeg`, spawned during downloads, inherit
   it too.
3. **`Nice=10`, `CPUWeight=50`, `IOWeight=50`** — video downloads won't
   starve other services of CPU or disk I/O.

If the kernel does kill the bot, systemd restarts it within five seconds
(`Restart=always`) — you only lose whatever video was mid-processing; just
resend the URL.

Verify the limits are active:

```bash
systemctl show fbig-bot -p MemoryMax -p MemorySwapMax -p OOMScoreAdjust
systemd-cgtop      # live usage, quit with 'q'
```

If you have another critical process on the same box that you want to
protect even further, you can lower **its** OOM score too (temporary, until
the process restarts — make it permanent via `OOMScoreAdjust=` in that
process's own systemd unit if it has one):

```bash
choom -n -500 -p "$(pgrep -f 'name-of-that-process')"
```

---

## 6. Caddy and HTTPS

```bash
cp /opt/fbig-bot/deploy/Caddyfile /etc/caddy/Caddyfile
nano /etc/caddy/Caddyfile     # fill in your domain and e-mail
systemctl reload caddy
```

Caddy requests a certificate from Let's Encrypt automatically — the first
attempt takes a few seconds:

```bash
systemctl status caddy
curl -s https://mybot.duckdns.org/health
```

If `/health` responds over HTTPS, the important part is done.

**If the certificate request times out:** double-check `dig +short
mybot.duckdns.org` actually returns your server's IP (see step 1) — a
mismatched DNS record is a very common cause, and Caddy's error message
("Timeout during connect... likely firewall problem") doesn't mention it.
The other common cause really is a firewall: many providers ship a cloud
firewall or a ufw-enabled image, so make sure ports 80 and 443 are open
from the outside.

---

## 7. DuckDNS — periodic refresh

DuckDNS lets inactive domains expire. A cron job confirms it every five
minutes. The script runs straight from `deploy/` so `update.sh` (git pull)
keeps it current — a copy elsewhere would silently go stale.

```bash
cat > /etc/duckdns.conf <<'EOF'
DUCKDNS_DOMAIN=mybot
DUCKDNS_TOKEN=paste-your-duckdns-token-here
EOF
chmod 600 /etc/duckdns.conf

/opt/fbig-bot/deploy/duckdns-refresh.sh      # should print "DuckDNS OK: ..."

crontab -e
# add this line:
# */5 * * * * /opt/fbig-bot/deploy/duckdns-refresh.sh >/dev/null
# (stdout only — keep stderr unredirected so cron can report failures)
```

---

## 8. Register the webhook

Now that HTTPS works, fill in `PUBLIC_URL` (left blank in step 4) and
restart — the bot registers its webhook with Telegram automatically on
startup:

```bash
sudo -u fbigbot nano /opt/fbig-bot/.env
# PUBLIC_URL=https://mybot.duckdns.org

systemctl restart fbig-bot
journalctl -u fbig-bot -n 20 --no-pager
```

Look for a line like
`[webhook] setWebhook https://mybot.duckdns.org/webhook -> ...`.

Verify with Telegram directly:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Expect your domain as the `url`, `pending_update_count` near zero, and an
empty `last_error_message`.

---

## 9. Verification checklist

- [ ] `systemctl status fbig-bot caddy` — both `active (running)`
- [ ] `curl -s https://mybot.duckdns.org/health` — responds
- [ ] `ss -tlnp | grep 8000` — listening only on `127.0.0.1`
- [ ] `systemctl show fbig-bot -p MemoryMax -p OOMScoreAdjust` — limits are set
- [ ] Telegram: `/id` responds
- [ ] Telegram: send a real Reel link → a reply comes back and a row appears
      in Google Sheets
- [ ] Telegram: `/help`, `/search <text>` (`/hledej`), `/dedup` (`/zkontroluj`)
- [ ] Map: `https://mybot.duckdns.org/map?token=<MAP_TOKEN>` shows pins **and** the map tiles
      themselves load (a watermarked/blank background usually means `CARTO_API_KEY` is
      missing/invalid, or it has a Referer allowlist configured that doesn't include this
      deployment's own domain — an unrestricted key works from anywhere. Pins still render
      either way, so check the tiles specifically, not just that the page loads)

---

## 10. Operations

**Logs:**

```bash
journalctl -u fbig-bot -f          # live
journalctl -u fbig-bot -n 100      # last 100 lines
journalctl -u fbig-bot --since "1 hour ago"
```

**Restart:**

```bash
systemctl restart fbig-bot
```

**Update:**

```bash
/opt/fbig-bot/deploy/update.sh
```

Pulls the latest code, installs any new dependencies, **upgrades yt-dlp**
and restarts the service. Update yt-dlp regularly — social platforms change
their formats and an old version simply stops being able to download.

**Resource usage:**

```bash
systemctl status fbig-bot | grep Memory
systemd-cgtop
```

---

## 11. Troubleshooting

**Service doesn't come up right after start.**
Usually a missing or wrong `.env` variable — the app crashes on import in
that case. `journalctl -u fbig-bot -n 50` shows the specific error
(`KeyError: 'TELEGRAM_BOT_TOKEN'`, `ValueError: TELEGRAM_ALLOWED_USERS ...`).

**Caddy won't issue a certificate.**
Check that `dig +short mybot.duckdns.org` returns your server's IP and that
nothing else is listening on ports 80/443 (`ss -tlnp | grep -E ':80|:443'`).
Let's Encrypt needs port 80 reachable from the outside.

**Caddy returns 502.**
The bot isn't running, or it's listening somewhere else. Check
`systemctl status fbig-bot` and `ss -tlnp | grep 8000`. `HOST`/`PORT` in
`.env` must match the address in `reverse_proxy` in the Caddyfile.

**Bot doesn't respond in Telegram, but `/health` works.**
The webhook points elsewhere. `getWebhookInfo` (step 8) shows the current
URL and any delivery error.

**Bot keeps getting killed for memory.**
`oom` or `Killed` shows up in the log. Check `systemd-cgtop`; if the bot
routinely hits 800 MB, raise `MemoryMax` in
`/etc/systemd/system/fbig-bot.service` and run
`systemctl daemon-reload && systemctl restart fbig-bot`. Alternatively,
lower `MAX_VIDEO_MINUTES` — long videos are the biggest memory users.

**Downloading from Instagram / YouTube stopped working.**
First try `/opt/fbig-bot/deploy/update.sh` (updates yt-dlp). If that
doesn't help, you'll need fresh cookies — both platforms require them more
often when requests come from a server IP. Diagnostics:
`https://mybot.duckdns.org/debug?token=<MAP_TOKEN>`.

---

## 12. One thing outside the scope of this guide

After following this guide, the bot itself sits behind Caddy
(`HOST=127.0.0.1`), but other services on the same server might not be
configured that way. It's worth checking what's actually reachable from the
internet:

```bash
ss -tlnp | grep -v '127.0.0.1\|::1'
```

Anything that shouldn't be public belongs either behind `127.0.0.1` or
behind a firewall (your hosting provider's, or `ufw` on the server itself —
don't assume one is configured unless you set it up).

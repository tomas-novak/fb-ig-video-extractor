#!/usr/bin/env bash
# Refresh the A record on DuckDNS.
#
# DuckDNS keeps its own record of the IP and lets it expire if the domain does not
# check in for a longer period. This script confirms it regularly – even when the
# server has a static IP it costs nothing and saves a webhook outage.
#
# It is run from where it lives in the repo so that update.sh (git pull) keeps it
# current – a copy placed elsewhere would stay forever as it was at install time.
#
# Installation:
#   echo "DUCKDNS_DOMAIN=your-name" | sudo tee /etc/duckdns.conf
#   echo "DUCKDNS_TOKEN=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" | sudo tee -a /etc/duckdns.conf
#   sudo chmod 600 /etc/duckdns.conf
#   sudo crontab -e
#     */5 * * * * /opt/fbig-bot/deploy/duckdns-refresh.sh >/dev/null
#   (stdout only – leave stderr alone so cron reports a failure)
#
# Detailed guide: docs/deploy-vps.md

set -euo pipefail

CONFIG="${DUCKDNS_CONFIG:-/etc/duckdns.conf}"

if [ -f "$CONFIG" ]; then
	# shellcheck source=/dev/null
	. "$CONFIG"
fi

if [ -z "${DUCKDNS_DOMAIN:-}" ] || [ -z "${DUCKDNS_TOKEN:-}" ]; then
	echo "Missing DUCKDNS_DOMAIN or DUCKDNS_TOKEN (looked for them in $CONFIG)." >&2
	exit 1
fi

# An empty ip= parameter means "take the IP this request came from".
RESPONSE=$(curl -fsS --max-time 20 \
	"https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=")

# DuckDNS replies with a plain "OK" or "KO" – curl's exit code does not tell them apart.
if [ "$RESPONSE" != "OK" ]; then
	echo "DuckDNS update failed (response: ${RESPONSE:-empty}). Check the domain and token." >&2
	exit 1
fi

echo "DuckDNS OK: ${DUCKDNS_DOMAIN}.duckdns.org"

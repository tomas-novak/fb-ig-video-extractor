#!/usr/bin/env bash
# Obnova A záznamu na DuckDNS.
#
# DuckDNS si vede vlastní záznam o IP a nechává ho vypršet, pokud se doména
# delší dobu neozve. Tenhle skript ho pravidelně potvrdí – i když má server
# statickou IP, stojí to nic a ušetří to výpadek webhooku.
#
# Spouští se z místa, kde leží v repu, aby ho update.sh (git pull) udržoval
# aktuální – kopie jinam by zůstala navždy taková, jaká byla při instalaci.
#
# Instalace:
#   echo "DUCKDNS_DOMAIN=tvuj-nazev" | sudo tee /etc/duckdns.conf
#   echo "DUCKDNS_TOKEN=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" | sudo tee -a /etc/duckdns.conf
#   sudo chmod 600 /etc/duckdns.conf
#   sudo crontab -e
#     */5 * * * * /opt/fbig-bot/deploy/duckdns-refresh.sh >/dev/null 2>&1
#
# Podrobný postup: docs/migration/01-phase-a-vps.md

set -euo pipefail

CONFIG="${DUCKDNS_CONFIG:-/etc/duckdns.conf}"

if [ -f "$CONFIG" ]; then
	# shellcheck source=/dev/null
	. "$CONFIG"
fi

if [ -z "${DUCKDNS_DOMAIN:-}" ] || [ -z "${DUCKDNS_TOKEN:-}" ]; then
	echo "Chybí DUCKDNS_DOMAIN nebo DUCKDNS_TOKEN (hledáno v $CONFIG)." >&2
	exit 1
fi

# Prázdný parametr ip= znamená "vezmi si IP, ze které přišel tenhle požadavek".
RESPONSE=$(curl -fsS --max-time 20 \
	"https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=")

# DuckDNS odpovídá prostým "OK" nebo "KO" – návratový kód curl to nerozliší.
if [ "$RESPONSE" != "OK" ]; then
	echo "DuckDNS update selhal (odpověď: ${RESPONSE:-prázdná}). Zkontroluj doménu a token." >&2
	exit 1
fi

echo "DuckDNS OK: ${DUCKDNS_DOMAIN}.duckdns.org"

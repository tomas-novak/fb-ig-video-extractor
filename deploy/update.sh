#!/usr/bin/env bash
# Aktualizace nasazené instance – náhrada za automatický deploy z Railway.
#
# Použití:
#   sudo /opt/fbig-bot/deploy/update.sh
#
# Co dělá:
#   1. stáhne novou verzi kódu z gitu
#   2. doinstaluje závislosti
#   3. aktualizuje yt-dlp (viz poznámka níže)
#   4. restartuje službu a zkontroluje, že naběhla
#
# Podrobný postup: docs/deploy-vps.md

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fbig-bot}"
SERVICE="${SERVICE:-fbig-bot}"
APP_USER="${APP_USER:-fbigbot}"

# Vše je zabalené ve funkci, která se volá až na posledním řádku souboru.
# Bash tak má celý skript načtený dřív, než ho git pull níže může přepsat –
# tenhle soubor je totiž součástí aktualizovaného repozitáře.
main() {
	cd "$APP_DIR"

	echo "==> Stahuji novou verzi kódu"
	sudo -u "$APP_USER" git pull --ff-only

	echo "==> Instaluji závislosti"
	sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet -r requirements.txt

	# yt-dlp je v requirements.txt připnutý na konkrétní verzi, ale sociální sítě
	# mění formáty průběžně a stará verze prostě přestane stahovat. Proto se tady
	# vždy vytáhne nejnovější. Musí to být až po instalaci requirements.txt,
	# jinak by ho pin stáhl zpátky dolů. Když se ukáže, že novější verze funguje
	# lépe, vyplatí se pin v requirements.txt v repu zvednout.
	echo "==> Aktualizuji yt-dlp"
	sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade yt-dlp

	echo "==> Restartuji službu"
	systemctl restart "$SERVICE"

	# Chvíli počkat, ať se stihne projevit případný pád při startu
	# (chybějící proměnná v .env shodí aplikaci hned při importu).
	sleep 5

	if systemctl is-active --quiet "$SERVICE"; then
		echo "==> Hotovo, služba běží."
		"$APP_DIR/venv/bin/python" -c "import yt_dlp; print('yt-dlp', yt_dlp.version.__version__)"
	else
		echo "==> CHYBA: služba neběží. Poslední logy:" >&2
		journalctl -u "$SERVICE" -n 30 --no-pager >&2
		exit 1
	fi
}

main "$@"

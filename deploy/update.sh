#!/usr/bin/env bash
# Update a deployed instance.
#
# Usage:
#   sudo /opt/fbig-bot/deploy/update.sh
#
# What it does:
#   1. pulls the new version of the code from git
#   2. installs dependencies
#   3. updates yt-dlp (see the note below)
#   4. restarts the service and checks that it came up
#
# Detailed guide: docs/deploy-vps.md

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fbig-bot}"
SERVICE="${SERVICE:-fbig-bot}"
APP_USER="${APP_USER:-fbigbot}"

# Everything is wrapped in a function that is only called on the last line of the
# file. That way bash has the whole script loaded before the git pull below can
# overwrite it – this file is itself part of the updated repository.
main() {
	cd "$APP_DIR"

	echo "==> Pulling the new version of the code"
	sudo -u "$APP_USER" git pull --ff-only

	echo "==> Installing dependencies"
	sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet -r requirements.txt

	# yt-dlp is pinned to a specific version in requirements.txt, but social networks
	# keep changing their formats and an old version simply stops downloading. That is
	# why the latest one is always pulled here. It has to happen after installing
	# requirements.txt, otherwise the pin would drag it back down. When a newer version
	# proves to work better, it is worth bumping the pin in requirements.txt in the repo.
	echo "==> Updating yt-dlp"
	sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade yt-dlp

	echo "==> Restarting the service"
	systemctl restart "$SERVICE"

	# Wait a moment so that a crash during startup has time to show
	# (a missing variable in .env brings the app down right at import time).
	sleep 5

	if systemctl is-active --quiet "$SERVICE"; then
		echo "==> Done, the service is running."
		"$APP_DIR/venv/bin/python" -c "import yt_dlp; print('yt-dlp', yt_dlp.version.__version__)"
	else
		echo "==> ERROR: the service is not running. Latest logs:" >&2
		journalctl -u "$SERVICE" -n 30 --no-pager >&2
		exit 1
	fi
}

main "$@"

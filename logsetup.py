"""Shared logging setup.

Unhandled failures used to only ever reach the operator as the bare str(e) sent to the
Telegram user (see main.py's process_video) or a print() line in the systemd journal -
no traceback, nothing kept around, nothing readable without root/journal access. This
adds a rotating log file next to the existing stdout/journal output, world-readable (like
.env already is on this deployment) so it can be read without root - and callers use
logging.exception()/logging.error() instead of swallowing exceptions, so a future failure
leaves a real trace instead of a one-line guess.

LOG_DIR is relative by default (same reasoning as THUMB_DIR in thumbnails.py): resolved
under the process's working directory so it lands in the right place on both the VPS
deploy and Docker without needing a path override in either.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.getenv("LOG_DIR", "data/logs")
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

# Guards against double setup: `uvicorn.run("main:app", ...)` re-imports main.py under the
# module name "main" even when it is already running as "__main__" (same file, same process,
# a second execution of its top-level code) - but this logsetup module itself is only ever
# loaded once into sys.modules, so a module-level flag here (unlike one in main.py) actually
# persists across that reimport and catches it. Without this, setup_logging() would run
# twice, attaching two independent handlers on the same file - every log line duplicated,
# and two RotatingFileHandler instances doing their own rollover on the same path can split
# or discard log history.
_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True
    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    # Not logging.basicConfig(): it silently no-ops once the root logger already has a
    # handler (e.g. uvicorn's own setup), which would drop the file handler entirely
    # depending on import order. Configuring the root logger directly always takes effect.
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(logging.StreamHandler())
    try:
        os.chmod(LOG_FILE, 0o644)
    except OSError:
        pass

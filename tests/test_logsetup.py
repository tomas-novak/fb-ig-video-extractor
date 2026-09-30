"""Tests for the rotating log file setup - the piece that lets a failure be
diagnosed after the fact instead of only ever reaching the operator as a bare
error message with no trace (see main.py's process_video / analyzer.py's
Gemini raw-response logging)."""
import importlib
import logging
import os
import stat

import pytest


@pytest.fixture
def tmp_log_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOG_DIR", "data/logs")
    import logsetup
    importlib.reload(logsetup)
    yield logsetup
    logging.shutdown()
    for h in list(logging.getLogger().handlers):
        logging.getLogger().removeHandler(h)


class TestSetupLogging:
    def test_creates_world_readable_log_file(self, tmp_log_dir):
        tmp_log_dir.setup_logging()
        assert os.path.exists(tmp_log_dir.LOG_FILE)
        mode = stat.S_IMODE(os.stat(tmp_log_dir.LOG_FILE).st_mode)
        assert mode & stat.S_IROTH, "log file must be readable by others (no root needed)"

    def test_exception_traceback_is_captured(self, tmp_log_dir):
        tmp_log_dir.setup_logging()
        logger = logging.getLogger("test_logsetup")
        try:
            raise ValueError("simulated failure")
        except ValueError:
            logger.exception("something failed")
        with open(tmp_log_dir.LOG_FILE) as f:
            content = f.read()
        assert "ValueError: simulated failure" in content
        assert "Traceback" in content

    def test_calling_twice_does_not_duplicate_handlers(self, tmp_log_dir):
        # uvicorn.run("main:app", ...) re-imports main.py under the module name "main"
        # even while it is already running as "__main__" - same file, same process, a
        # second execution of its top-level code, so setup_logging() actually gets
        # called twice in a real deployment. Without a guard this would attach two
        # independent handlers on the same file (every line logged twice, and two
        # RotatingFileHandlers doing their own rollover on one path can split/discard
        # history).
        tmp_log_dir.setup_logging()
        first_count = len(logging.getLogger().handlers)
        tmp_log_dir.setup_logging()
        assert len(logging.getLogger().handlers) == first_count

        logger = logging.getLogger("test_logsetup_idempotent")
        logger.info("one line")
        with open(tmp_log_dir.LOG_FILE) as f:
            matching_lines = [line for line in f.read().splitlines() if "one line" in line]
        assert len(matching_lines) == 1

    def test_http_client_request_urls_are_not_logged(self, tmp_log_dir):
        # The Telegram Bot API embeds the bot token directly in the request URL
        # (api.telegram.org/bot<TOKEN>/method), and httpx/httpcore log that full URL at
        # INFO by default - attached to the root logger, that would write live secrets
        # into this deliberately world-readable file. Real problems (warnings/errors)
        # from these loggers must still come through.
        tmp_log_dir.setup_logging()
        for name in ("httpx", "httpcore", "urllib3"):
            logger = logging.getLogger(name)
            logger.info('HTTP Request: POST https://api.telegram.org/botFAKE_TOKEN_123/x "200 OK"')
            logger.warning("a real problem from %s", name)
        with open(tmp_log_dir.LOG_FILE) as f:
            content = f.read()
        assert "FAKE_TOKEN_123" not in content
        assert content.count("a real problem from") == 3

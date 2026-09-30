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

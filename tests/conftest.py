"""Shared test fixtures for ATWA."""

import os
from pathlib import Path

import pytest

from config.paths import ensure_dirs


@pytest.fixture(autouse=True)
def _isolate_test_env(monkeypatch):
    """Force ATWA_ENV=test for every test and reset ATWA_OVERRIDE_ vars."""
    monkeypatch.setenv("ATWA_ENV", "test")
    # Clean up any ATWA_OVERRIDE_ vars that might leak between tests
    for key in list(os.environ):
        if key.startswith("ATWA_OVERRIDE_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(scope="session", autouse=True)
def clean_test_env():
    """Wipe the test environment's database and logs before the test session.

    Mirrors the production conftest pattern from the design doc.
    """
    base = Path.home() / ".atwa" / "test"
    db_path = base / "atwa.db"
    if db_path.exists():
        db_path.unlink()
    for f in (base / "logs").rglob("*.log"):
        f.unlink(missing_ok=True)
    ensure_dirs("test")
    yield

"""Tests for config.paths and config.loader."""

import os
from pathlib import Path

import pytest

from config.loader import _cast, deep_merge, load_config
from config.paths import ensure_dirs, get_base_dir, get_paths


# ── paths.py ──────────────────────────────────────────────


class TestGetBaseDir:
    def test_production(self):
        result = get_base_dir("production")
        assert result == Path.home() / ".atwa" / "production"

    def test_development(self):
        result = get_base_dir("development")
        assert result == Path.home() / ".atwa" / "development"

    def test_test(self):
        result = get_base_dir("test")
        assert result == Path.home() / ".atwa" / "test"


class TestGetPaths:
    def test_returns_all_expected_keys(self):
        paths = get_paths("production")
        expected = {
            "base", "db", "log_dir", "pty_dir", "tmp_dir",
            "daemon_log", "server_log", "daemon_pid", "server_pid",
        }
        assert set(paths.keys()) == expected

    def test_db_under_base(self):
        paths = get_paths("production")
        assert paths["db"] == paths["base"] / "atwa.db"

    def test_pty_dir_under_log_dir(self):
        paths = get_paths("production")
        assert paths["pty_dir"] == paths["log_dir"] / "pty"

    def test_pid_files_under_tmp_dir(self):
        paths = get_paths("production")
        assert paths["daemon_pid"].parent == paths["tmp_dir"]
        assert paths["server_pid"].parent == paths["tmp_dir"]

    def test_different_envs_isolated(self):
        prod = get_paths("production")
        dev = get_paths("development")
        assert prod["db"] != dev["db"]
        assert prod["log_dir"] != dev["log_dir"]


class TestEnsureDirs:
    def test_creates_missing_dirs(self, tmp_path, monkeypatch):
        base = tmp_path / "atwa-test"
        monkeypatch.setattr(
            "config.paths.get_base_dir", lambda env: base
        )
        ensure_dirs("test")
        assert (base / "logs" / "pty").is_dir()
        assert (base / "tmp").is_dir()

    def test_idempotent(self, tmp_path, monkeypatch):
        base = tmp_path / "atwa-test"
        monkeypatch.setattr(
            "config.paths.get_base_dir", lambda env: base
        )
        ensure_dirs("test")
        ensure_dirs("test")  # should not raise
        assert (base / "logs" / "pty").is_dir()


# ── loader.py ─────────────────────────────────────────────


class TestDeepMerge:
    def test_flat_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        assert deep_merge(base, override) == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"section": {"x": 1, "y": 2}}
        override = {"section": {"y": 99}}
        result = deep_merge(base, override)
        assert result["section"]["x"] == 1
        assert result["section"]["y"] == 99

    def test_new_key_added(self):
        base = {"a": 1}
        override = {"b": 2}
        assert deep_merge(base, override) == {"a": 1, "b": 2}

    def test_does_not_mutate_base(self):
        base = {"s": {"x": 1}}
        original = base.copy()
        deep_merge(base, {"s": {"x": 99}})
        assert base == original


class TestCast:
    def test_int(self):
        assert _cast("42", 0) == 42

    def test_float(self):
        assert _cast("0.92", 0.0) == pytest.approx(0.92)

    def test_bool_true(self):
        for val in ("true", "True", "1", "yes"):
            assert _cast(val, True) is True

    def test_bool_false(self):
        for val in ("false", "False", "0", "no"):
            assert _cast(val, True) is False

    def test_str_fallback(self):
        assert _cast("hello", None) == "hello"


class TestLoadConfig:
    def test_default_values(self):
        """Loading production should match default.toml values."""
        cfg = load_config("production")
        assert cfg["env"]["name"] == "production"
        assert cfg["server"]["port"] == 8742
        assert cfg["log"]["level"] == "INFO"

    def test_development_overrides(self):
        cfg = load_config("development")
        assert cfg["env"]["name"] == "development"
        assert cfg["server"]["port"] == 8743
        assert cfg["log"]["level"] == "DEBUG"
        # Unoverridden values should come from default
        assert cfg["daemon"]["scrollback_lines"] == 200

    def test_test_overrides(self):
        cfg = load_config("test")
        assert cfg["env"]["name"] == "test"
        assert cfg["server"]["port"] == 8744
        assert cfg["insight_engine"]["enabled"] is False
        assert cfg["tmux"]["socket"] == "atwa_test"

    def test_atwa_env_fallback(self, monkeypatch):
        """When no env is passed, use ATWA_ENV env var."""
        monkeypatch.setenv("ATWA_ENV", "development")
        cfg = load_config()
        assert cfg["env"]["name"] == "development"

    def test_env_var_override(self, monkeypatch):
        """ATWA_OVERRIDE_SERVER_PORT=9000 should override server.port."""
        monkeypatch.setenv("ATWA_OVERRIDE_SERVER_PORT", "9000")
        cfg = load_config("production")
        assert cfg["server"]["port"] == 9000

    def test_env_var_override_bool(self, monkeypatch):
        monkeypatch.setenv("ATWA_OVERRIDE_INSIGHT_ENGINE_ENABLED", "false")
        cfg = load_config("production")
        assert cfg["insight_engine"]["enabled"] is False

    def test_env_var_override_float(self, monkeypatch):
        monkeypatch.setenv("ATWA_OVERRIDE_THRESHOLDS_STUCK_SIMILARITY", "0.80")
        cfg = load_config("production")
        assert cfg["thresholds"]["stuck_similarity"] == pytest.approx(0.80)

    def test_production_pool_size(self):
        cfg = load_config("production")
        assert cfg["database"]["pool_size"] == 10

    def test_default_pool_size(self):
        """Non-production envs should inherit default pool_size=5."""
        cfg = load_config("development")
        assert cfg["database"]["pool_size"] == 5

"""Path resolution for ATWA runtime directories.

All runtime artifacts (database, logs, PTY recordings, temp files) are
converged under ``~/.atwa/<env>/``.  Code must use ``get_paths()`` to
obtain paths — never hard-code absolute paths.
"""

from pathlib import Path


def get_base_dir(env: str) -> Path:
    """Root directory for all runtime files: ``~/.atwa/<env>/``."""
    return Path.home() / ".atwa" / env


def get_paths(env: str) -> dict[str, Path]:
    """Return a dict of resolved paths for the given environment."""
    base = get_base_dir(env)
    return {
        "base": base,
        "db": base / "atwa.db",
        "log_dir": base / "logs",
        "pty_dir": base / "logs" / "pty",
        "tmp_dir": base / "tmp",
        "daemon_log": base / "logs" / "daemon.log",
        "server_log": base / "logs" / "server.log",
        "daemon_pid": base / "tmp" / "daemon.pid",
        "server_pid": base / "tmp" / "server.pid",
    }


def ensure_dirs(env: str) -> None:
    """Create all required directories for *env* if they don't exist."""
    paths = get_paths(env)
    for key in ("log_dir", "pty_dir", "tmp_dir"):
        paths[key].mkdir(parents=True, exist_ok=True)

"""Centralized logging setup for the ATWA server.

Consumes the ``[log]`` config section and the ``server_log`` path
from ``config/paths.py`` to configure Python's ``logging`` module.
"""

import logging
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.loader import load_config
from config.paths import get_paths

_CONFIGURED_ATTR = "_atwa_configured"


def setup_logging(env: str | None = None) -> None:
    """Configure root and server loggers based on config.

    - Reads ``cfg["log"]["level"]``, ``cfg["log"]["max_bytes"]``,
      ``cfg["log"]["backup_count"]``
    - Adds a :class:`RotatingFileHandler` pointing at ``paths["server_log"]``
    - Adds a :class:`StreamHandler` for console output
    - Idempotent: calling twice does not add duplicate handlers
    """
    cfg = load_config(env)
    paths = get_paths(cfg["env"]["name"])

    log_cfg = cfg["log"]
    level_name = str(log_cfg["level"]).upper()
    level = getattr(logging, level_name, logging.INFO)
    max_bytes = int(log_cfg["max_bytes"])
    backup_count = int(log_cfg["backup_count"])

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()

    # Idempotency guard
    if getattr(root, _CONFIGURED_ATTR, False):
        return

    root.setLevel(level)

    # Console handler
    console = StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler
    log_path: Path = paths["server_log"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    setattr(root, _CONFIGURED_ATTR, True)

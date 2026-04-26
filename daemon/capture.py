"""Dual-mode output capture for tmux panes."""

import logging
import re
from pathlib import Path

import libtmux
import pyte

from config.loader import load_config
from config.paths import get_paths

logger = logging.getLogger(__name__)

# Regex patterns for ANSI sequences that pyte may miss
_CSI_PATTERN = re.compile(r"\x1b\[[0-9;]*[mGKHFJABCDsuhr]")
_OSC_PATTERN = re.compile(r"\x1b\][^\x07]*\x07")


def clean_ansi_output(raw: str) -> str:
    """Strip ANSI escape sequences from raw terminal output.

    Uses pyte first for proper terminal emulation, then falls back
    to regex for private sequences pyte may miss.
    Returns empty string for empty input.
    """
    if not raw:
        return ""

    try:
        line_count = raw.count("\n") + 1
        height = min(max(line_count, 24), 1000)
        screen = pyte.Screen(220, height)
        stream = pyte.Stream(screen)
        stream.feed(raw)
        lines = [screen.display[i] for i in range(screen.lines)]
        result = "\n".join(line.rstrip() for line in lines if line.strip())
        if result:
            return result
    except Exception:
        pass

    # Regex fallback
    clean = _CSI_PATTERN.sub("", raw)
    clean = _OSC_PATTERN.sub("", clean)
    return clean


def get_pty_log_path(pane_id: str, env: str | None = None) -> Path:
    """Return PTY log path for a pane: ``~/.atwa/<env>/logs/pty/pane-<id>.log``.

    The ``%`` prefix is stripped from pane_id.
    """
    cfg = load_config(env)
    env_name = cfg["env"]["name"]
    paths = get_paths(env_name)
    clean_id = pane_id.lstrip("%")
    return paths["pty_dir"] / f"pane-{clean_id}.log"


def capture_pane_output(pane_id: str, scrollback: int | None = None) -> str:
    """Capture visible output from a tmux pane via capture-pane.

    Returns cleaned text, or empty string if pane is not accessible.
    """
    cfg = load_config()
    socket = cfg["tmux"]["socket"] or None
    if scrollback is None:
        scrollback = cfg["daemon"]["scrollback_lines"]

    try:
        server = libtmux.Server(socket_name=socket)
        for session in server.sessions:
            for window in session.windows:
                for pane in window.panes:
                    if pane.pane_id == pane_id:
                        raw = pane.cmd(
                            "capture-pane", "-p", "-S", f"-{scrollback}"
                        ).stdout
                        if isinstance(raw, str):
                            return clean_ansi_output(raw)
                        return clean_ansi_output("\n".join(raw))
        return ""
    except Exception as e:
        logger.warning("Failed to capture pane %s: %s", pane_id, e)
        return ""


def read_pty_log(pane_id: str, env: str | None = None) -> str:
    """Read and clean the PTY log file for a pane.

    Returns empty string if the file does not exist.
    """
    path = get_pty_log_path(pane_id, env)
    if not path.exists():
        return ""
    try:
        raw = path.read_text(errors="replace")
        return clean_ansi_output(raw)
    except Exception as e:
        logger.warning("Failed to read PTY log for pane %s: %s", pane_id, e)
        return ""


def rotate_pty_log(path: Path, env: str | None = None) -> None:
    """Rotate a PTY log file when it exceeds ``pty.max_bytes``.

    Keeps ``pty.backup_count`` backup copies (``.1``, ``.2``, ``.3``).
    """
    if not path.exists():
        return

    cfg = load_config(env)
    max_bytes = cfg["pty"]["max_bytes"]
    backup_count = cfg["pty"]["backup_count"]

    if path.stat().st_size < max_bytes:
        return

    # Delete the oldest backup if it exists
    oldest = Path(f"{path}.{backup_count}")
    if oldest.exists():
        oldest.unlink()

    # Shift existing backups up by one
    for i in range(backup_count - 1, 0, -1):
        src = Path(f"{path}.{i}")
        if src.exists():
            src.rename(Path(f"{path}.{i + 1}"))

    # Move current log to .1
    path.rename(Path(f"{path}.1"))


def get_capture_interval(is_active: bool, env: str | None = None) -> float:
    """Return polling interval in seconds based on pane activity state."""
    cfg = load_config(env)
    key = "capture_interval_active_ms" if is_active else "capture_interval_idle_ms"
    return cfg["daemon"][key] / 1000.0

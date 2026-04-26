"""Utility functions for the ATWA daemon."""

import time


def now_ms() -> int:
    """Return current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)

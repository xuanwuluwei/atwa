"""ATWA configuration package."""

from config.loader import load_config
from config.paths import ensure_dirs, get_base_dir, get_paths

__all__ = ["load_config", "get_paths", "get_base_dir", "ensure_dirs"]

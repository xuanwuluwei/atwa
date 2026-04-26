"""Configuration loading for ATWA.

Loading order (later wins):
1. ``config/default.toml`` — baseline values
2. ``config/<env>.toml`` — environment-specific overrides (deep-merged)
3. ``ATWA_OVERRIDE_*`` environment variables — runtime overrides

Environment resolution:
``ATWA_ENV`` env var  >  ``--env`` CLI arg  >  default ``production``
"""

import os
import tomllib
from pathlib import Path


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a new dict.

    Nested dicts are merged recursively; all other types are replaced
    by the override value.
    """
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _cast(value: str, reference):
    """Cast *value* to the same type as *reference* (for env-var overrides).

    Falls back to ``str`` if *reference* is ``None`` or an unrecognised type.
    """
    if reference is None:
        return value
    if isinstance(reference, bool):
        return value.lower() in ("true", "1", "yes")
    if isinstance(reference, int):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value


def load_config(env: str | None = None) -> dict:
    """Load and return the full configuration dict for *env*.

    *env* defaults to the ``ATWA_ENV`` environment variable, or
    ``"production"`` if that is also unset.
    """
    env = env or os.getenv("ATWA_ENV", "production")
    config_dir = Path(os.getenv("ATWA_CONFIG_DIR", "config"))

    # 1. Baseline
    with open(config_dir / "default.toml", "rb") as f:
        cfg = tomllib.load(f)

    # 2. Environment overlay (deep-merge)
    env_file = config_dir / f"{env}.toml"
    if env_file.exists():
        with open(env_file, "rb") as f:
            env_cfg = tomllib.load(f)
        cfg = deep_merge(cfg, env_cfg)

    # 3. ATWA_OVERRIDE_<SECTION>_<KEY>=value
    #    Section names may contain underscores (e.g. insight_engine),
    #    so we try each split point from right to left and match against
    #    known sections in the config.
    for key, val in os.environ.items():
        if not key.startswith("ATWA_OVERRIDE_"):
            continue
        raw = key[14:].lower()
        # Try splitting at each underscore from right to left
        matched = False
        pos = raw.rfind("_")
        while pos > 0 and not matched:
            section, field = raw[:pos], raw[pos + 1:]
            if section in cfg:
                cfg[section][field] = _cast(val, cfg[section].get(field))
                matched = True
            pos = raw.rfind("_", 0, pos)

    cfg["env"]["name"] = env
    return cfg

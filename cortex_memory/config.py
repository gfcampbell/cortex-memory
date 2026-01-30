"""Configuration management for Cortex Memory."""

import os
import yaml
from pathlib import Path

# Default config location
CORTEX_HOME = Path(os.environ.get("CORTEX_HOME", "~/.cortex")).expanduser()
CONFIG_PATH = CORTEX_HOME / "config.yaml"
ENV_PATH = CORTEX_HOME / ".env"

DEFAULT_CONFIG = {
    "database": {
        "path": str(CORTEX_HOME / "data" / "cortex.db")
    },
    "vector": {
        "path": str(CORTEX_HOME / "data" / "chroma"),
        "collection": "cortex_memories"
    },
    "analysis": {
        "provider": "anthropic",
        "model": "claude-haiku-4-5",
        "memory_window": 200
    },
    "context": {
        "ttl_days": 7,
        "max_open_loops": 5,
        "max_memories": 10
    },
    "consolidation": {
        "decay_rate": 0.95,
        "consolidate_after_days": 7,
        "min_importance": 0.1
    },
    "service": {
        "host": "127.0.0.1",
        "port": 8420
    }
}

_config = None


def load_env():
    """Load .env file from CORTEX_HOME."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().strip().split("\n"):
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def get_config() -> dict:
    """Load and return configuration, merging defaults with user config."""
    global _config
    if _config is not None:
        return _config

    load_env()

    config = DEFAULT_CONFIG.copy()

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, user_config)

    _config = config
    return config


def save_config(config: dict):
    """Save configuration to disk."""
    global _config
    CORTEX_HOME.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    _config = config


def save_env(key: str, value: str):
    """Save or update a value in the .env file."""
    CORTEX_HOME.mkdir(parents=True, exist_ok=True)
    
    lines = []
    replaced = False
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().strip().split("\n"):
            if line.startswith(f"{key}="):
                lines.append(f"{key}={value}")
                replaced = True
            else:
                lines.append(line)
    
    if not replaced:
        lines.append(f"{key}={value}")
    
    ENV_PATH.write_text("\n".join(lines) + "\n")
    os.environ[key] = value


def get_seed_entities_path() -> Path:
    return CORTEX_HOME / "seed_entities.yaml"


def is_initialized() -> bool:
    return CONFIG_PATH.exists()


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

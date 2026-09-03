"""Create a client-safe config without credentials or private endpoint IDs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


SECRET_KEYS = {
    "api_key",
    "access_key",
    "secret_key",
    "password",
    "token",
    "refresh_token",
    "private_key",
}


def sanitize(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if lowered in SECRET_KEYS or lowered.endswith(("_api_key", "_secret", "_password", "_token")):
        return ""
    if lowered == "endpoints":
        return {}
    if lowered == "endpoint" and isinstance(value, str) and value.startswith("ep-"):
        return ""
    if isinstance(value, dict):
        return {item_key: sanitize(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str) and value.startswith("ep-"):
        return ""
    return value


def main() -> None:
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    clean = sanitize(raw)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(clean, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path


def parse_secret_file(secrets_path: Path) -> dict[str, str]:
    configured: dict[str, str] = {}
    if not secrets_path.is_file():
        return configured
    for raw_line in secrets_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        if normalized_key and normalized_value:
            configured[normalized_key] = normalized_value
    return configured

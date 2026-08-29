from __future__ import annotations

from pathlib import Path

DATA_SOURCE_SECRET_ADAPTERS = {
    "EIA_API_KEY": "eia",
    "EXA_API_KEY": "exa",
    "TAVILY_API_KEY": "tavily",
    "TUSHARE_TOKEN": "tushare",
}
ALLOWED_DATA_SOURCE_SECRET_KEYS = frozenset(DATA_SOURCE_SECRET_ADAPTERS)


def parse_data_source_secrets(secrets_path: Path) -> dict[str, str]:
    configured: dict[str, str] = {}
    if not secrets_path.is_file():
        return configured
    with secrets_path.open(encoding="utf-8") as secrets_file:
        for raw_line in secrets_file:
            separator_index = raw_line.find("=")
            if separator_index < 0:
                continue
            normalized_key = raw_line[:separator_index].strip()
            if normalized_key not in ALLOWED_DATA_SOURCE_SECRET_KEYS:
                continue
            normalized_value = raw_line[separator_index + 1 :].strip()
            if normalized_value:
                configured[normalized_key] = normalized_value
    return configured

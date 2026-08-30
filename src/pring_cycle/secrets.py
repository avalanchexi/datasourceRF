from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from tempfile import mkstemp

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


def migrate_data_source_secrets(
    source_path: Path,
    destination_path: Path,
) -> dict[str, object]:
    if not source_path.is_file():
        raise ValueError("secret_source_not_found")
    if not destination_path.is_file():
        raise ValueError("runtime_secrets_file_not_initialized")
    imported = parse_data_source_secrets(source_path)
    if not imported:
        raise ValueError("supported_data_source_secrets_missing")
    configured = {**parse_data_source_secrets(destination_path), **imported}
    contents = "".join(
        f"{key}={configured.get(key, '')}\n"
        for key in sorted(ALLOWED_DATA_SOURCE_SECRET_KEYS)
    )
    descriptor, temporary_name = mkstemp(
        dir=destination_path.parent,
        prefix=f".{destination_path.name}.",
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
            secret_file.write(contents)
            secret_file.flush()
            os.fsync(secret_file.fileno())
        temporary_path.replace(destination_path)
        destination_path.chmod(0o600)
    except BaseException:
        with suppress(OSError):
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
        raise
    configured_adapters = {
        adapter: "enabled" if key in configured else "disabled"
        for key, adapter in sorted(DATA_SOURCE_SECRET_ADAPTERS.items())
    }
    return {
        "configured": configured_adapters,
        "migrated_adapters": sorted(
            DATA_SOURCE_SECRET_ADAPTERS[key] for key in imported
        ),
        "network_requests": 0,
        "status": "ok",
    }

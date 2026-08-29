from __future__ import annotations

from pathlib import Path

from pring_cycle.secrets import (
    ALLOWED_DATA_SOURCE_SECRET_KEYS,
    parse_data_source_secrets,
)


def test_only_data_source_credentials_cross_the_secret_parser_boundary(tmp_path: Path) -> None:
    secrets_path = tmp_path / "secrets.env"
    secrets_path.write_text(
        "OPENAI_API_KEY=model-provider-secret\n"
        "TUSHARE_TOKEN=data-source-secret\n"
        "UNKNOWN_TOKEN=unknown-secret\n",
        encoding="utf-8",
    )

    assert (
        frozenset({"EIA_API_KEY", "EXA_API_KEY", "TAVILY_API_KEY", "TUSHARE_TOKEN"})
        == ALLOWED_DATA_SOURCE_SECRET_KEYS
    )
    assert parse_data_source_secrets(secrets_path) == {"TUSHARE_TOKEN": "data-source-secret"}

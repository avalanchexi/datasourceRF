from __future__ import annotations

from pathlib import Path

import pytest

from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_certification import (
    _source_history_identities,
    create_source_certified_candidate,
)
from pring_cycle.source_history import _validated_discovered_url


def test_smoke_success_cannot_recertify_the_audited_invalid_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    official = {
        "lpr": "d" * 64,
        "official-context:omo": "e" * 64,
        "source-history": "f" * 64,
    }
    monkeypatch.setattr(
        "pring_cycle.source_certification.verify_source_smoke_artifacts",
        lambda *_args, **_kwargs: {
            "core": "a" * 64,
            "tushare-context": "b" * 64,
            "tushare-market": "c" * 64,
            **official,
        },
    )

    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        create_source_certified_candidate(
            paths,
            target_business_date="2026-08-28",
            source_smoke_hashes=("a" * 64,),
            personal_noncommercial_use_approved=True,
        )
    assert all(
        not model.model_version_id.startswith("model-v0011-")
        for model in ModelRepository(paths.database).list_versions()
    )


def test_source_certification_requires_explicit_tushare_use_boundary(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    with pytest.raises(
        ValueError,
        match="tushare_personal_noncommercial_use_must_be_confirmed",
    ):
        create_source_certified_candidate(
            paths,
            target_business_date="2026-08-28",
            source_smoke_hashes=("a" * 64,),
            personal_noncommercial_use_approved=False,
        )


def test_source_history_identities_require_url_period_and_family() -> None:
    assert _source_history_identities(
        {
            "records": [
                {
                    "source_url": "https://official.example/releases/1",
                    "period": "2026-08",
                    "families": ["nbs_gdp"],
                },
                {
                    "source_url": "https://official.example/releases/2",
                    "period": "2026-08-20",
                    "lpr": True,
                },
            ]
        }
    ) == {
        ("https://official.example/releases/1", "2026-08", "nbs_gdp"),
        ("https://official.example/releases/2", "2026-08-20", "lpr"),
    }


def test_source_history_rejects_cross_origin_discovered_links_before_fetch() -> None:
    with pytest.raises(ValueError, match="source_history_discovered_url_invalid"):
        _validated_discovered_url(
            "https://www.pbc.gov.cn",
            "https://attacker.example/redirect",
            expected_host="www.pbc.gov.cn",
        )

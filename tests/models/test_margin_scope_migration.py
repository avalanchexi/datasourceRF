"""Public candidate admission for the approved two-exchange margin identity.

The Beijing Stock Exchange refuses the public endpoints this project can reach (403, and a
self-redirecting 302 on the replacement entry), so ``CN_MARGIN_BALANCE`` -- whose required
members are scoped ``all_exchanges`` -- can never be certified as it is defined. The approved
disposition is a new identity that says what it actually measures, not a residual: see
docs/adr/0016-certification-gate-escape-valve-is-catalog-membership.md.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.candidate_admission import _hash
from pring_cycle.catalog import metric_definition
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.metric_contracts import REQUIRED_DIMENSION_MEMBERS
from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.models.test_candidate_admission import (
    bind_synthetic_review,
    prepared_request,
    save,
    submit,
)

NEW_ID = "CN_MARGIN_BALANCE_SSE_SZSE"


def migrated_request(paths: RuntimePaths) -> dict[str, Any]:
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    old = next(d for d in manifest["metric_definitions"] if d["metric_id"] == "CN_MARGIN_BALANCE")
    replacement = {
        **old,
        "metric_id": NEW_ID,
        "name_cn": "沪深两所融资余额与买入额",
        "source_codes": ["SSE_SZSE_MARGIN_BALANCE"],
        "release_event_family": "cn_margin_balance_sse_szse",
    }
    manifest["metric_identity_migration"] = {
        "version": "margin-two-exchange-scope-v0001",
        "replacements": {"CN_MARGIN_BALANCE": NEW_ID},
        "removed_metric_ids": [],
        "history_policy": "retain_separate",
    }
    manifest["metric_definitions"] = [
        replacement if d["metric_id"] == "CN_MARGIN_BALANCE" else d
        for d in manifest["metric_definitions"]
    ]
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    # A renamed P1 is still required coverage, so the reviewed package has to certify the new
    # identity by name. bind_synthetic_review only rebinds the manifest and review hashes.
    bindings = package["definition_bindings"]
    bindings.pop("CN_MARGIN_BALANCE")
    bindings[NEW_ID] = _hash(replacement)
    bind_synthetic_review(paths, request, package)
    return request


def test_two_exchange_margin_identity_replaces_the_all_exchange_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The new identity enters the catalog in place of the old, and stays P1.

    Dropping Beijing is not a parameter change: the required members carry
    ``scope: all_exchanges`` (metric_contracts.py), and by CONTEXT.md an economic fact's
    identity is its definition version, period and canonical dimensions together. So the
    two-exchange reading has to be its own metric, and the catalog must stop offering the
    old id rather than quietly narrowing what it means.
    """
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = migrated_request(paths)

    submit(paths, save(paths, request))

    admitted = json.loads(capsys.readouterr().out)
    assert admitted["status"] == "candidate", admitted

    manifest = ModelRepository(paths.database).manifest(admitted["model_version_id"])
    ids = {d["metric_id"]: d for d in manifest["metric_definitions"]}
    assert NEW_ID in ids
    assert "CN_MARGIN_BALANCE" not in ids
    # Demoting it to P2 would have let an acquisition failure hide behind a priority label.
    assert ids[NEW_ID]["priority"] == "P1"
    assert sum(1 for d in ids.values() if d["priority"] == "P1") == 42


def test_the_two_exchange_identity_declares_two_exchange_members() -> None:
    """The members say sse_szse, so a three-exchange total can never satisfy it by accident."""
    members = REQUIRED_DIMENSION_MEMBERS[NEW_ID]
    assert {member["scope"] for member in members} == {"sse_szse"}
    assert {member["measure"] for member in members} == {
        "financing_balance",
        "financing_buy_amount",
    }


def test_migration_keeps_the_three_exchange_history_and_refuses_to_reuse_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The old total stays readable, and nothing lets it become the two-exchange figure.

    This is the whole point of a new identity rather than a narrowed one. An all-exchange
    balance and a Shanghai-plus-Shenzhen balance are different economic facts, so the old
    claims keep their own id and the new id starts empty -- no splicing, no back-writing,
    and above all no residual: the new figure has to be delivered, not subtracted.
    """
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    evidence = EvidenceRepository(paths.database)
    at = datetime(2026, 9, 17, 12, tzinfo=UTC)
    definition = metric_definition("CN_MARGIN_BALANCE", definition_version="metric-catalog-v0001")
    claim = SourceClaimInput(
        metric_id="CN_MARGIN_BALANCE",
        definition_version=definition.definition_version,
        period_kind="business_day",
        period_start="2026-09-11",
        period_end="2026-09-11",
        # The catalog definition carries no dimensions; the scope lives in the selection
        # contract (REQUIRED_DIMENSION_MEMBERS), which is what makes the id the identity.
        dimensions={},
        value=1_900_000_000_000.0,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit=definition.unit,
        provider="tushare",
        source_reference="synthetic:legacy:CN_MARGIN_BALANCE",
        release_event_id="synthetic:legacy:CN_MARGIN_BALANCE:2026-09-11",
        release_at=None,
        public_available_at=None,
        fetched_at=at,
        available_at=at,
        certification_status="awaiting_source_certification",
        quality_status="validated",
    )
    stored = evidence.append_source_claim(claim)
    before = evidence.trace(stored.observation_id, mode=AsOfMode.SYSTEM, as_of=at)

    request = migrated_request(paths)
    submit(paths, save(paths, request))
    admitted = json.loads(capsys.readouterr().out)
    manifest = ModelRepository(paths.database).manifest(admitted["model_version_id"])
    catalog_version = manifest["metric_catalog_version"]

    assert evidence.trace(stored.observation_id, mode=AsOfMode.SYSTEM, as_of=at) == before
    assert before.claims[0].value == claim.value
    # The retired id cannot be written into the new catalog at all.
    with pytest.raises(KeyError, match="unknown_metric_id"):
        evidence.append_source_claim(replace(claim, definition_version=catalog_version))
    # NOTE: this asserts the *absence* of a delivery contract, so when the two-exchange
    # adapter lands this assertion must be retargeted at that contract's own rejection
    # (wrong scope), not deleted -- the behaviour being pinned is "an old row cannot become
    # the new fact by relabelling", which outlives the missing adapter.
    # Nor can the old total be relabelled as the two-exchange figure. The claim below is
    # built to satisfy every incidental check -- the new id, its catalog version, its own
    # unit -- so that what rejects it is the delivery contract itself, not a unit typo.
    migrated_definition = next(
        d for d in manifest["metric_definitions"] if d["metric_id"] == NEW_ID
    )
    with pytest.raises(ValueError, match="registered_source_contract_not_implemented"):
        evidence.append_source_claim(
            replace(
                claim,
                metric_id=NEW_ID,
                definition_version=catalog_version,
                unit=migrated_definition["unit"],
                dimensions=dict(REQUIRED_DIMENSION_MEMBERS[NEW_ID][0]),
            )
        )
    assert (
        evidence.metric_series(
            NEW_ID, mode=AsOfMode.SYSTEM, as_of=at, definition_version=catalog_version
        )
        == ()
    )


def test_the_new_identity_cannot_keep_the_retired_source_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A new name over the old delivery path is the failure this migration exists to prevent.

    Renaming the metric is the whole point only if the new id also stops pointing at the
    three-exchange source. A manifest that takes the new id but keeps the retired
    ``source_codes`` or release family would certify a two-exchange fact against an
    all-exchange delivery -- the residual by another route.
    """
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = migrated_request(paths)
    definition = next(
        d for d in request["manifest"]["metric_definitions"] if d["metric_id"] == NEW_ID
    )
    definition["source_codes"] = ["CN_MARGIN_BALANCE"]
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    package["definition_bindings"][NEW_ID] = _hash(definition)
    bind_synthetic_review(paths, request, package)

    with pytest.raises(SystemExit):
        submit(paths, save(paths, request))
    assert "certification_margin_scope_identity_mismatch" in capsys.readouterr().err


def test_the_new_identity_cannot_keep_the_retired_release_family(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sibling of the source-path counterexample, for the other half of the delivery identity.

    ``source_codes`` says where a value comes from and ``release_event_family`` says which
    publication it belongs to. Either one left pointing at the three-exchange delivery would
    reattach the new metric to the old one, so both have to be refused, not just the first.
    """
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = migrated_request(paths)
    definition = next(
        d for d in request["manifest"]["metric_definitions"] if d["metric_id"] == NEW_ID
    )
    definition["release_event_family"] = "cn_margin_balance"
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    package["definition_bindings"][NEW_ID] = _hash(definition)
    bind_synthetic_review(paths, request, package)

    with pytest.raises(SystemExit):
        submit(paths, save(paths, request))
    assert "certification_margin_scope_identity_mismatch" in capsys.readouterr().err

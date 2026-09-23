"""Core history consumes formula warmup at the first formal result's cutoff."""

from datetime import UTC, datetime

from pring_cycle.model_evaluation import evaluate_history
from tests.models.test_core_formula_warmup import capture_core, prepare_core_runtime
from tests.models.test_fixed_window_preflight import calendar_runtime as calendar_runtime


def test_history_accepts_warmup_published_before_its_formal_consumer(
    calendar_runtime, capsys
):
    paths, _ = calendar_runtime
    candidate, version, historical_day = prepare_core_runtime(paths, capsys)
    capture_core(
        paths,
        version,
        "CN_BOND_CORE_000012",
        [historical_day],
        published=lambda _: datetime(2026, 4, 1, 8, tzinfo=UTC),
    )

    # The pre-window price is known at the first formal result, even though it
    # was not known on its own historical date. This is the approved PUBLIC rule.
    result = evaluate_history(
        paths.database,
        candidate,
        requested_start="2026-04-01",
        requested_end="2026-04-01",
    )

    assert result.evaluated_days == 1
    assert result.input_days == 140
    assert result.input_range_start == "2025-08-29"
    assert set(result.core_outputs_by_day) == {"2026-04-01"}
    # A flat history supplies the base calculation without confirming a state.
    assert result.core_states_by_day["2026-04-01"] == (None, None, None)

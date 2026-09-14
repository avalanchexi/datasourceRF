"""Exploratory probe for ticket 19: how far does a complete synthetic candidate get today?

Isolated native runtime only. Real core transport bytes (core-transport-196) are acquired through the
public TuShare core adapter; PUBLIC times are synthetic and marked as such. No real source is certified,
nothing touches the formal runtime, and this probe is not an acceptance test.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path('/mnt/d/cursor/datasourceRF')
sys.path.insert(0, str(ROOT))
RECORDS = ROOT / '.scratch/pring-data-acquisition-repair'
TRANSPORT = RECORDS / 'core-transport-196'
WORK = Path('/home/tywin/.cache/pring-cycle/verification/probe19-20260914')

from pring_cycle.acquisition import AcquisitionRepository  # noqa: E402
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput  # noqa: E402
from pring_cycle.model_evaluation import calibrate_model, replay_models  # noqa: E402
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository  # noqa: E402
from pring_cycle.runtime import RuntimePaths, initialize_runtime  # noqa: E402
from pring_cycle.source_adapters import CORE_API_IDENTITIES, TushareCoreAdapter  # noqa: E402
from tests.models.test_candidate_admission import prepared_request, save, submit  # noqa: E402


def log(**event: object) -> None:
    event['at'] = datetime.now(UTC).isoformat()
    print(json.dumps(event, ensure_ascii=False, default=str), flush=True)


def main() -> None:
    run = WORK / datetime.now(UTC).strftime('%Y%m%dT%H%M%S')
    paths = RuntimePaths.discover(run / 'runtime')
    initialize_runtime(paths)
    receipts = {r['name']: r for r in json.loads((TRANSPORT / 'receipts.json').read_text())['receipts']}
    calendar_rows = json.loads((TRANSPORT / receipts['calendar']['local_file']).read_bytes())['data']['items']
    days = sorted(date.fromisoformat(f'{d[:4]}-{d[4:6]}-{d[6:]}') for d, is_open in calendar_rows if is_open == 1)
    log(step='calendar', trading_days=len(days), first=days[0], last=days[-1])

    models = ModelRepository(paths.database)
    # Existing isolated-test bootstrap of the builtin comparison baseline, as in test_candidate_replay.
    models.record_acceptance('model-v0001', CALIBRATION_BASELINE)
    models.activate('model-v0001', explicitly_approved=True)

    request, _ = prepared_request(paths)
    import contextlib
    import io
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        submit(paths, save(paths, request))
    candidate_id = json.loads(out.getvalue())['model_version_id']
    version = request['manifest']['metric_catalog_version']
    log(step='admitted', candidate=candidate_id, catalog=version)

    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    evidence = EvidenceRepository(paths.database)
    started = time.monotonic()
    for metric_id, (api, code) in CORE_API_IDENTITIES.items():
        raw = (TRANSPORT / receipts[metric_id]['local_file']).read_bytes()
        rows = {r[1]: r for r in json.loads(raw)['data']['items']}

        def transport(payload: dict[str, object], body: bytes = raw) -> bytes:
            return body

        acquired = TushareCoreAdapter('probe-token', transport=transport).acquire_core_bars(
            acquisitions, metric_id, start=days[0], end=days[-1], expected_business_dates=tuple(days)
        )
        receipt = acquired.receipt
        assert receipt.received_at is not None
        claims = []
        for catalog in (version, 'metric-catalog-v0001'):
            for day in days:
                close = float(rows[day.strftime('%Y%m%d')][2])
                published = datetime(day.year, day.month, day.day, 8, tzinfo=UTC)
                linked = catalog == version
                claims.append(SourceClaimInput(
                    metric_id=metric_id, definition_version=catalog, period_kind='business_day',
                    period_start=day.isoformat(), period_end=day.isoformat(), dimensions={},
                    value=close, value_state=EvidenceValueState.REPORTED_VALUE, unit='index_points',
                    provider='tushare' if linked else 'fixture',
                    source_reference=f'tushare:{api}:{code}:{day.isoformat()}' if linked
                    else f'fixture:metric-catalog-v0001:{metric_id}:{day.isoformat()}',
                    release_event_id=f'synthetic:probe19-core-public:{catalog}:{metric_id}:{day.isoformat()}',
                    release_at=published, public_available_at=published,
                    fetched_at=receipt.received_at if linked else published,
                    available_at=datetime.now(UTC) if linked else published,
                    certification_status='certified', quality_status='validated',
                    **({'acquisition_id': receipt.acquisition_id} if linked else {}),
                ))
        evidence.append_source_claims(tuple(claims))
        log(step='core_imported', metric=metric_id, claims=len(claims), seconds=round(time.monotonic() - started, 1))

    for model_id in (candidate_id,):
        t = time.monotonic()
        try:
            results = calibrate_model(paths.database, model_id)
            summary = {k: results[k] for k in (*CALIBRATION_BASELINE, 'evaluated_days', 'input_days', 'input_range_start')}
            accepted = models.record_acceptance(model_id, results)
            log(step='calibration', model=model_id, passed=accepted.passed, summary=summary, seconds=round(time.monotonic() - t, 1))
        except Exception as error:  # probe: record and continue to replay diagnostics
            log(step='calibration_error', model=model_id, error=repr(error), seconds=round(time.monotonic() - t, 1))

    t = time.monotonic()
    try:
        replay = replay_models(paths.database, candidate_id, 'model-v0001', requested_start='2026-03-09', requested_end='2026-08-28')
        gaps = list(replay.gaps)
        (RECORDS / 'probe-19-lifecycle-20260914-gaps.json').write_text(json.dumps(gaps, ensure_ascii=False, indent=2))
        log(step='replay', quality=replay.quality_passed, days=replay.evaluated_trading_days, gap_count=len(gaps),
            gaps_head=gaps[:40], seconds=round(time.monotonic() - t, 1))
    except Exception as error:
        log(step='replay_error', error=repr(error), seconds=round(time.monotonic() - t, 1))


if __name__ == '__main__':
    main()

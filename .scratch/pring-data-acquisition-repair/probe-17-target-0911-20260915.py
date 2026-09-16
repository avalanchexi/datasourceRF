"""Probe: registered full run for target 2026-09-11 on a material copy, core extended synthetically.

argv: checkout root, material dir, destination runtime. Prints run outcome and incomplete gaps.
"""
import json, resource, shutil, sys, time
from collections import Counter
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, sys.argv[1])
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.worker import process_pending_run
from tests.integration.test_worker_registered_catalog import real_core_opener

EXTRA = ['20260831', '20260901', '20260902', '20260903', '20260904',
         '20260907', '20260908', '20260909', '20260910', '20260911']
base = real_core_opener()


class Opener:
    def open(self, request, *, timeout):
        payload = json.loads(request.data)
        document = json.loads(base.open(request, timeout=timeout).read())
        params = payload['params']
        fields = document['data']['fields']
        items = document['data']['items']
        date_index = fields.index('cal_date' if payload['api_name'] == 'trade_cal' else 'trade_date')
        if payload['api_name'] != 'trade_cal':
            # The last archived close, even when the requested range starts after the archive.
            archived = json.loads(base.open(type(request)(request.full_url, data=json.dumps(
                {**payload, 'params': {**params, 'start_date': '20170101', 'end_date': '20260828'}}
            ).encode()), timeout=timeout).read())['data']['items']
            latest = max(archived, key=lambda item: item[date_index])
        added = []
        for day in EXTRA:
            if params['start_date'] <= day <= params['end_date']:
                if payload['api_name'] == 'trade_cal':
                    row = {'cal_date': day, 'is_open': 1}
                else:
                    # Flat synthetic sessions continuing the last archived close.
                    close = latest[fields.index('close')]
                    row = {'ts_code': params['ts_code'], 'trade_date': day, 'close': close,
                           'pre_close': close, 'pct_chg': 0.0}
                added.append([row[f] for f in fields])
        # Archived rows are newest first.
        document['data']['items'] = sorted(added, key=lambda item: item[date_index], reverse=True) + items
        return BytesIO(json.dumps(document).encode())


class Failing:
    def open(self, request, *, timeout):
        raise OSError('probe source unavailable')


material, destination = Path(sys.argv[2]), Path(sys.argv[3])
shutil.rmtree(destination, ignore_errors=True)
shutil.copytree(material / 'runtime', destination)
paths = RuntimePaths.discover(destination)
paths.secrets.write_text('TUSHARE_TOKEN=fixture-only\n', encoding='utf-8')
paths.secrets.chmod(0o600)
candidate = json.loads((material / 'material.json').read_text())['candidate_model_version_id']
runs = RunRepository(paths.database)
run = runs.submit_manual_full(target_business_date='2026-09-11', client_request_id='probe-0911',
                              model_version_id=candidate, system_as_of=datetime.now(UTC))
started = time.monotonic()
with mock.patch('pring_cycle.source_adapters.build_opener', lambda *h: Opener()), \
        mock.patch('pring_cycle.tushare_context.build_opener', lambda *h: Failing()):
    process_pending_run(paths, report_adapters=())
stored = runs.get(run.run_id)
print(json.dumps({'seconds': round(time.monotonic() - started, 1),
                  'peak_rss_mb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
                  'status': stored.status, 'step': stored.current_step,
                  'error': stored.error_classification, 'projection': stored.projection_set_id},
                 default=str))
plan = runs.full_retrieval_plan(run.run_id)
final = plan.get('final') or plan.get('initial') or {}
gaps = [g for g in final.get('gaps', []) if not g.get('complete')]
print('incomplete gaps', len(gaps))
print(json.dumps(Counter((g['metric_id'], g.get('priority'), g.get('reason', g.get('status'))) for g in gaps).most_common(80), default=str, indent=0))
print(json.dumps(gaps[:5], default=str, indent=1))

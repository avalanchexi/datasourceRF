"""Bounded request/document pilot; no evidence claims, model qualification or activation."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import runpy
import signal
import sqlite3
import sys
from time import monotonic
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.http_transport import open_no_redirects
from pring_cycle.models import ModelRepository
from pring_cycle.retrieval_ledger import RetrievalLedger, daily_consumption
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_discovery import MAX_SEARCH_RESPONSE_BYTES, SearchHttpResponse, search_discovery_adapter
from pring_cycle.secrets import parse_data_source_secrets


ROOT = Path(__file__).resolve().parent
LIMITS = {'tavily': 16, 'exa': 8}
MAX_DOCUMENT_BYTES = 4_000_000


@contextmanager
def network_deadline(deadline: float):
    remaining = min(15.0, deadline - monotonic())
    if remaining <= 0:
        raise TimeoutError('pilot_network_deadline')
    def expired(_signal, _frame):
        raise TimeoutError('pilot_network_deadline')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def save_new(path: Path, value: object) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.write('\n')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan_bytes = args.plan.read_bytes()
    plan = json.loads(plan_bytes)
    assert plan['phase'] == 'request_document_pilot_no_model_evaluation'
    assert plan['sample_count'] == len(plan['samples']) == 4
    assert plan['search_requests_per_provider'] == 4
    assert plan['candidate_limit'] == 3
    assert plan['target_business_date'] == '2026-08-28'
    assert len({s['sample_id'] for s in plan['samples']}) == 4
    assert all(len(s['query']) <= 800 for s in plan['samples'])
    assert not args.runtime_root.exists(), 'fresh runtime required; never restart this pilot'
    output = args.output.resolve()
    assert output.parent == ROOT and not output.exists()
    preflight = runpy.run_path(str(ROOT / 'search-preexperiment-preflight.py'))['preflight']
    initial = preflight()
    assert all(initial['configured'].values())
    assert initial['today_consumed'] is not None
    assert initial.get('active_or_queued_runs') == 0, 'default runtime has pending activity'
    assert all(initial['today_consumed'][p] + 4 <= LIMITS[p] for p in LIMITS)
    source_secrets = Path(initial['runtime']['secrets'])
    keys = parse_data_source_secrets(source_secrets)
    paths = RuntimePaths.discover(args.runtime_root)
    assert paths.database != Path(initial['runtime']['database'])
    output.mkdir()
    (output / 'plan.json').write_bytes(plan_bytes)
    save_new(output / 'preflight.json', initial)
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    # Built-in identity is only bookkeeping for this pilot, never a qualified
    # repaired candidate. No run is sent to the worker and no model is activated.
    manifest = models.manifest('model-v0001')
    cutoff = datetime.now(UTC)
    start_day = cutoff.astimezone(ZoneInfo('Asia/Shanghai')).date()
    save_new(output / 'frozen.json', {
        'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(),
        'executor_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'preflight_sha256': hashlib.sha256((ROOT / 'search-preexperiment-preflight.py').read_bytes()).hexdigest(),
        'started_at': cutoff, 'runtime': paths.as_document(),
        'bookkeeping_model_id': 'model-v0001',
        'bookkeeping_manifest': manifest,
        'definition_version': manifest['metric_catalog_version'],
        'model_qualification_evaluated': False,
        'model_usable_completion_rate': None,
        'production_writes': 0,
        'max_search_requests': 8, 'max_document_requests': 24,
    })
    runs = RunRepository(paths.database)
    ledger = RetrievalLedger(paths.database)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    paired = []
    started = monotonic()
    deadline = started + 600
    stop_reason = None
    for sample_index, sample in enumerate(plan['samples']):
        run = runs.submit(
            command_type='targeted_refresh', target_business_date=plan['target_business_date'],
            client_request_id=sample['sample_id'], model_version_id='model-v0001',
            system_as_of=cutoff, release_event_id='pilot:' + sample['sample_id'],
            metric_ids=(sample['metric_id'],), period=sample['period'],
        )
        ledger.bind_run(run, manifest['metric_catalog_version'])
        save_new(output / (sample['sample_id'] + '-run.json'), {'run_id': run.run_id})
        provider_order = ('tavily', 'exa') if sample_index % 2 == 0 else ('exa', 'tavily')
        for provider in provider_order:
            entry = {'sample_id': sample['sample_id'], 'provider': provider,
                     'arm_id': f"{sample['sample_id']}:{provider}", 'run_id': run.run_id,
                     'query': sample['query'], 'candidate_sources': []}
            # Recheck the production and pilot ledgers together. A new runtime
            # does not reset the account's observed daily budget.
            current = preflight()
            with sqlite3.connect(paths.database) as connection:
                connection.row_factory = sqlite3.Row
                own = daily_consumption(connection, datetime.now(UTC))
            entry['budget_before'] = {'default_runtime': current['today_consumed'], 'pilot': own}
            within_budget = current['today_consumed'] is not None and (
                current['today_consumed'][provider] + own[provider] < LIMITS[provider]
            )
            if (not within_budget or current.get('active_or_queued_runs') != 0
                    or monotonic() - started > 600
                    or datetime.now(UTC).astimezone(ZoneInfo('Asia/Shanghai')).date() != start_day):
                stop_reason = 'pilot_budget_activity_or_deadline_stop'
            if stop_reason:
                entry.update(status='not_attempted', classification=stop_reason)
            else:
                before = monotonic()
                def search_transport(endpoint, headers, payload):
                    assert endpoint in ('https://api.tavily.com/search', 'https://api.exa.ai/search')
                    entry['transport_started_at'] = datetime.now(UTC).isoformat()
                    request = Request(endpoint, headers=headers, method='POST',
                                      data=json.dumps(payload, ensure_ascii=False).encode())
                    with network_deadline(deadline):
                        try:
                            with open_no_redirects(request, timeout=15) as http:
                                entry['observed_http_status'] = int(http.status)
                                raw = http.read(MAX_SEARCH_RESPONSE_BYTES + 1)
                                return SearchHttpResponse(int(http.status), None, raw, dict(http.headers))
                        except HTTPError as error:
                            entry['observed_http_status'] = int(error.code)
                            return SearchHttpResponse(int(error.code), None,
                                                      error.read(MAX_SEARCH_RESPONSE_BYTES + 1), dict(error.headers))
                try:
                    response = search_discovery_adapter(
                        provider, keys['TAVILY_API_KEY' if provider == 'tavily' else 'EXA_API_KEY'],
                        sample['query'], paths=paths, run_id=run.run_id, ledger=ledger,
                        verify_candidates=None, transport=search_transport,
                    )('pilot:' + sample['sample_id'])
                    entry.update(asdict(response))
                except Exception as error:
                    entry.update(status='failed', classification='pilot_transport_or_execution_failure',
                                 error_type=type(error).__name__)
                    if isinstance(getattr(error, 'partial', None), bytes):
                        partial = error.partial[:MAX_SEARCH_RESPONSE_BYTES + 1]
                        entry['partial_response_sha256'] = hashlib.sha256(partial).hexdigest()
                        entry['partial_response_bytes'] = len(partial)
                        entry['raw_status'] = 'incomplete_transport_body_not_a_retained_original'
                    snapshot = ledger.for_run(run.run_id)
                    outstanding = [r for r in snapshot['requests'] if r['state'] == 'reserved'
                                   and r['channel'] == provider]
                    for physical in outstanding:
                        ledger.complete(physical['request_id'], outcome='failed',
                                        classification='pilot_transport_or_execution_failure',
                                        status=entry.get('observed_http_status'))
                entry['elapsed_seconds'] = monotonic() - before
                if entry.get('classification') in {
                    'authentication_failed', 'forbidden_unknown', 'rate_limited', 'quota_exhausted',
                    'event_daily_limit', 'daily_limit', 'run_limit', 'negative_cache_active',
                }:
                    stop_reason = 'pilot_provider_or_budget_gate'
                entry.pop('candidate_summaries', None)
                entry.pop('evidence', None)
            save_new(output / (entry['arm_id'].replace(':', '-') + '-search.json'), entry)
            paired.append(entry)
            print(json.dumps({'sample': sample['sample_id'], 'provider': provider,
                              'status': entry['status']}, ensure_ascii=False), flush=True)
        runs.mark_action_required(run.run_id, 'pilot_no_model_evaluation')
        save_new(output / (sample['sample_id'] + '-ledger.json'), ledger.for_run(run.run_id))
    # Both search arms are complete before any candidate is downloaded. No
    # candidate document writes claims or changes the other arm's initial gap.
    downloads = []
    downloaded_urls = {}
    samples = {s['sample_id']: s for s in plan['samples']}
    for entry in paired:
        sample = samples[entry['sample_id']]
        for index, url in enumerate(dict.fromkeys(entry.get('candidate_sources', ()))):
            if index >= 3:
                break
            parsed = urlsplit(url)
            item = {'arm_id': entry['arm_id'], 'candidate_index': index, 'url': url,
                    'original_validity': 'not_evaluated', 'model_evaluation': 'not_evaluated'}
            try:
                port_allowed = parsed.port in (None, 443)
            except ValueError:
                port_allowed = False
            if (parsed.scheme != 'https' or parsed.hostname not in sample['allowed_hosts']
                    or parsed.username or parsed.password or not port_allowed):
                item.update(status='not_attempted', reason='outside_frozen_official_hosts')
            elif url in plan['known_prior_candidates']:
                item.update(status='known_prior_candidate', prior_evidence=plan['known_prior_candidates'][url])
            elif url in downloaded_urls:
                item.update(status='shared_url_reuse', shared_download=downloaded_urls[url])
            elif stop_reason:
                item.update(status='not_attempted', reason=stop_reason)
            elif monotonic() - started > 600:
                item.update(status='not_attempted', reason='pilot_time_limit')
            else:
                receipt_ids = []
                metadata = {}

                def fetch() -> bytes:
                    request = Request(url, headers={'User-Agent': 'Mozilla/5.0',
                                                   'Accept': 'text/html,application/json,application/pdf'})
                    with open_no_redirects(request, timeout=15) as response:
                        metadata.update(http_status=int(response.status),
                                        media_type=response.headers.get('Content-Type', ''))
                        return response.read(MAX_DOCUMENT_BYTES + 1)

                def screen(raw: bytes) -> dict[str, object]:
                    if len(raw) > MAX_DOCUMENT_BYTES:
                        raise ValueError('pilot_document_size_limit')
                    # HTTP success alone does not qualify the source, period or value.
                    return {**metadata, 'bytes': len(raw), 'validation': 'manual_review_pending'}

                before = monotonic()
                try:
                    with network_deadline(deadline):
                        acquired = acquisitions.capture(
                            provider='official_preexperiment', api_name='https_get',
                            parameters={'url': url, 'arm_id': entry['arm_id']}, fields='raw_document',
                            parser_version='pilot-document-capture-v1', fetch=fetch, parse=screen,
                            normalize=lambda value: value, on_started=receipt_ids.append,
                            max_error_body_bytes=MAX_DOCUMENT_BYTES,
                        )
                    item.update(status='received', **acquired.value)
                except Exception as error:
                    item.update(status='failed', error_type=type(error).__name__)
                    if isinstance(getattr(error, 'partial', None), bytes):
                        partial = error.partial[:MAX_DOCUMENT_BYTES + 1]
                        digest = hashlib.sha256(partial).hexdigest()
                        (output / digest).write_bytes(partial)
                        item.update(partial_response_sha256=digest, truncated=True)
                    if isinstance(getattr(error, 'code', None), int):
                        item['http_status'] = error.code
                        item['location'] = error.headers.get('Location') if error.headers else None
                item.update(elapsed_seconds=monotonic() - before, acquisition_ids=receipt_ids)
                for identity in receipt_ids:
                    receipt = acquisitions.get(identity)
                    item['receipt'] = asdict(receipt)
                    if receipt.raw_hash:
                        raw = acquisitions.read_content(identity, 'raw')
                        destination = output / receipt.raw_hash
                        if not destination.exists():
                            destination.write_bytes(raw)
                        assert hashlib.sha256(destination.read_bytes()).hexdigest() == receipt.raw_hash
                downloaded_urls[url] = {'arm_id': entry['arm_id'], 'candidate_index': index,
                                        'acquisition_ids': receipt_ids}
            downloads.append(item)
            save_new(output / (entry['arm_id'].replace(':', '-') + f'-document-{index}.json'), item)
            print(json.dumps({'arm': entry['arm_id'], 'candidate': index, 'status': item['status']},
                             ensure_ascii=False), flush=True)
    save_new(output / 'result.json', {
        'phase': plan['phase'], 'search_arms': paired, 'documents': downloads,
        'model_evaluation': 'not_evaluated', 'model_usable_completion_rate': None,
        'source_certification_grants': 0, 'model_activations': 0, 'production_writes': 0,
        'finished_at': datetime.now(UTC), 'elapsed_seconds': monotonic() - started,
        'search_originals': 'Runtime CAS only; inspect through acquisition read_content before 30-day expiry',
    })


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        # On interruption or an unexpected failure, preserve the frozen slots
        # and all completed arm records. Never fill missing slots by retrying.
        try:
            output = Path(sys.argv[sys.argv.index('--output') + 1])
            if output.is_dir() and (output / 'frozen.json').is_file():
                plan = json.loads((output / 'plan.json').read_bytes())
                slots = []
                for sample in plan['samples']:
                    run_file = output / (sample['sample_id'] + '-run.json')
                    frozen = json.loads((output / 'frozen.json').read_bytes())
                    snapshot = (RetrievalLedger(Path(frozen['runtime']['database'])).for_run(
                        json.loads(run_file.read_bytes())['run_id']) if run_file.is_file() else None)
                    for provider in ('tavily', 'exa'):
                        arm = f"{sample['sample_id']}-{provider}"
                        record = output / (arm + '-search.json')
                        physical = [r for r in snapshot['requests'] if r['channel'] == provider] if snapshot else []
                        slots.append(json.loads(record.read_bytes()) if record.is_file() else {
                            'sample_id': sample['sample_id'], 'provider': provider,
                            'status': 'unknown_completion' if physical else 'not_attempted',
                            'reason': 'interrupted_without_final_arm_record',
                            'physical_requests': physical,
                        })
                save_new(output / 'interrupted.json', {
                    'error_type': type(error).__name__, 'search_slots': slots,
                    'model_evaluation': 'not_evaluated', 'production_writes': 0,
                })
        except Exception:
            pass  # Existing frozen plan and native acquisition receipts remain intact.
        raise

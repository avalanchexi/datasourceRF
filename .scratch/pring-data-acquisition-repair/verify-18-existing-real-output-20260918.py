"""Review the retained real CLI output on a copy; make no new provider call."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = Path('/tmp/datasourceRF-current-verify-20260918-v2/site')
SOURCE_DB = Path('/home/tywin/.cache/pring-cycle/verification/repair-18-real-20260916b-codex_cli/reports.sqlite3')
DEST = ROOT / 'evidence-18-review-20260918'
RECEIPT = ROOT / 'verification-18-existing-real-output-20260918.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fact(pointer: str, value: object) -> dict:
    return {'pointer': pointer, 'value': value}


def main() -> None:
    started = time.monotonic()
    assert not DEST.exists(), 'A repeat requires a new separately identified review directory'
    inputs = [SOURCE_DB, ROOT / 'evidence-18/real-20260916b-codex_cli.json', ROOT / 'evidence-18/real-20260916b-bundle.json', ROOT / 'evidence-18/frozen-bundle.json', Path(__file__)]
    inputs += sorted((SITE / 'pring_cycle').rglob('*.py'))
    before_hashes = {str(p): sha(p) for p in inputs}
    for suffix in ('-wal', '-shm', '-journal'):
        assert not SOURCE_DB.with_name(SOURCE_DB.name + suffix).exists()
    original = json.loads(inputs[3].read_bytes())
    saved = json.loads(inputs[1].read_bytes())
    document = json.loads(inputs[2].read_bytes())
    assert sha(inputs[3]) == '44e6f39226dada99b01a1b7fceb68f61a9be715404b50d27da3110bd2e6ab7ba'
    assert saved['scope'] == 'historical_core_explanation_only'
    assert saved['full_bundle_explanation_passed'] is False
    assert saved['production_writes'] == 0 and saved['formal_publication'] is False
    snapshot_id = saved['result']['report_snapshot_id']
    expected_hash = '975975a32b3765d44a23b977d588d5852e04e1529aa6b81780aa3a778eb81c5e'
    with sqlite3.connect(SOURCE_DB.as_uri() + '?mode=ro&immutable=1', uri=True) as c:
        stored_bundle = c.execute('SELECT document_json,bundle_hash FROM evidence_bundle WHERE bundle_id=?', (document['bundle_id'],)).fetchone()
        stored_body = c.execute('SELECT body_json FROM report_snapshot WHERE report_snapshot_id=?', (snapshot_id,)).fetchone()[0]
        assert c.execute('SELECT COUNT(*) FROM report_explanation_review').fetchone()[0] == 0
    assert json.loads(stored_bundle[0]) == document
    assert digest(document) == stored_bundle[1] == saved['snapshot']['bundle_hash']
    assert json.loads(stored_body) == saved['snapshot']['body']
    original_assets = original['structured_context']['change_reasons']['core_assets']
    extracted = [{k: asset[k] for k in ('asset', 'metric_id', 'state', 'latest_business_date')} | {'evidence_id': asset['observation_version_ids'][-1]} for asset in original_assets]
    assert document['structured_context']['core_asset_facts'] == extracted
    assert document['structured_context']['source_frozen_bundle_id'] == original['bundle_id']
    for key in ('projection_set_id', 'target_business_date', 'report_cutoff', 'system_as_of', 'model_version_id', 'trend_rule_version', 'current_stage', 'stage_reason', 'core_states', 'support', 'governance_gaps'):
        assert document[key] == original[key], key
    assert document['counterevidence'][:-1] == original['counterevidence']
    assert set(document['allowed_evidence_ids']) == {x['evidence_id'] for x in extracted}
    assert document['allowed_governance_refs'] == original['allowed_governance_refs']
    assert saved['result']['status'] == 'completed'
    assert len(saved['attempts']) == 1
    attempt = saved['attempts'][0]
    assert attempt['outcome'] == 'succeeded' and attempt['tool_events'] == 0
    assert attempt['process_audit']['exit_code'] == 0
    assert attempt['output_hash'] == expected_hash == attempt['process_audit']['output_file_sha256']
    recovered_output = {key: document[key] for key in ('bundle_id', 'current_stage', 'report_cutoff')}
    recovered_output.update(sections=saved['snapshot']['body']['ai_explanation'], proxy_used=False)
    assert digest(recovered_output) == expected_hash
    assert len(canonical(recovered_output).encode()) == attempt['process_audit']['output_file_bytes']
    for section in recovered_output['sections']:
        assert set(section['evidence_ids']) <= set(document['allowed_evidence_ids'])
        assert set(section['governance_refs']) <= set(document['allowed_governance_refs'])
    sys.path.insert(0, str(SITE))
    from pring_cycle.reports import EvidenceBundle, ReportRepository
    kwargs = {k: v for k, v in document.items() if k not in ('bundle_id', 'schema_version', 'prompt_version')}
    for key in ('report_cutoff', 'system_as_of'):
        kwargs[key] = datetime.fromisoformat(kwargs[key])
    bundle = EvidenceBundle.create(**kwargs)
    assert json.loads(canonical(bundle.document())) == document
    skeleton = bundle.deterministic_skeleton()
    assert {k: v for k, v in saved['snapshot']['body'].items() if k not in ('ai_explanation', 'explanation_verification')} == skeleton
    sections = [
        {
            'index': 0, 'verdict': 'supported',
            'assessment': '逐句核对目标日和三项核心资产末日均为2026-08-03、三状态均bull、P0通过声明、stage_iii及canonical_combination，均与冻结包一致。三个证据ID逐一对应冻结原包末日观测，模型引用在白名单内。末句明确仅描述历史包；P1/P2不足和冲突不支持推广为当前市场或新的来源认证，也未被用来重分正式阶段。此处认可对既有包的解释，不重新认证包内原始市场事实。',
            'support': [fact('/target_business_date', '2026-08-03'), fact('/core_states', {'bond': 'bull', 'stock': 'bull', 'commodity': 'bull'}), fact('/structured_context/core_asset_facts', extracted), fact('/support/0', '三核心资产价格状态通过 P0 门禁。'), fact('/current_stage', 'stage_iii'), fact('/stage_reason', 'canonical_combination')],
            'counterevidence': [fact('/counterevidence/0', 'p1_evidence_incomplete:34/42'), fact('/counterevidence/1', 'p2_evidence_incomplete:2/13'), fact('/counterevidence/5', '历史目录已被来源审查隔离；本段仅解释旧记录，不证明当前市场或新来源认证。')],
        },
        {
            'index': 1, 'verdict': 'supported',
            'assessment': '34/42、2/13、政策传导冲突、库存冲突及P2降级逐项对应冻结包治理缺口；范围限制对应明确explanation_scope。该段无观测ID引用，只陈述包内治理元数据，以下JSON Pointer单独绑定支持事实。三核心P0通过是仍成立的相反方向证据，不能据此补足被省略事实；原文没有作此推断。',
            'support': [fact('/governance_gaps', ['p1_evidence_incomplete:34/42', 'p2_evidence_incomplete:2/13', 'policy_context_degraded:transmission_conflict', 'inventory_context_degraded:conflict', 'p2_context_degraded']), fact('/structured_context/explanation_scope', '仅历史三核心状态和治理限制；不解释被省略的宏观、库存或派生值。')],
            'counterevidence': [fact('/support/0', '三核心资产价格状态通过 P0 门禁。'), fact('/current_stage', 'stage_iii')],
        },
        {
            'index': 2, 'verdict': 'supported',
            'assessment': '2026-08-31 20:51:41.285300 UTC精确对应report_cutoff；三个latest_business_date和目标日都是2026-08-03，因此截点不等于观测日期。历史隔离及不证明当前市场/新来源认证逐字受包内counterevidence约束；无新增行情数字或交易指令。P0通过及stage_iii只支持该历史包，不能反证为当前适用。治理说明由包内元数据支持，不假称新增独立来源认证。',
            'support': [fact('/report_cutoff', '2026-08-31T20:51:41.285300+00:00'), fact('/target_business_date', '2026-08-03'), fact('/structured_context/core_asset_facts/0/latest_business_date', '2026-08-03'), fact('/structured_context/core_asset_facts/1/latest_business_date', '2026-08-03'), fact('/structured_context/core_asset_facts/2/latest_business_date', '2026-08-03'), fact('/counterevidence/5', '历史目录已被来源审查隔离；本段仅解释旧记录，不证明当前市场或新来源认证。')],
            'counterevidence': [fact('/support/0', '三核心资产价格状态通过 P0 门禁。'), fact('/current_stage', 'stage_iii')],
        },
    ]
    DEST.mkdir()
    copy = DEST / 'reports.sqlite3'
    shutil.copy2(SOURCE_DB, copy)
    reports = ReportRepository.create(copy)
    prior = reports.get(snapshot_id)
    prior_attempts = reports.attempts(snapshot_id)
    assert prior.body == saved['snapshot']['body']
    assert prior_attempts[0].output_hash == expected_hash
    assert prior.explanation_verification['status'] == 'pending_evidence_review'
    review = reports.record_explanation_review(snapshot_id, output_hash=expected_hash, reviewer='Codex /root documented semantic review 2026-09-18', sections=sections)
    after = reports.get(snapshot_id)
    assert after.body == prior.body and after.bundle_hash == prior.bundle_hash
    assert reports.attempts(snapshot_id) == prior_attempts
    assert len(reports.explanation_reviews(snapshot_id)) == 1
    assert after.explanation_verification == review and review['status'] == 'passed'
    with sqlite3.connect(copy) as c:
        assert c.execute('SELECT body_json FROM report_snapshot WHERE report_snapshot_id=?', (snapshot_id,)).fetchone()[0] == stored_body
        c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    assert before_hashes == {str(p): sha(p) for p in inputs}
    (DEST / 'paragraph-review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
    (DEST / 'snapshot-after-review.json').write_text(json.dumps(asdict(after), ensure_ascii=False, indent=2, default=str) + '\n')
    out = {'state': 'finished', 'result': 'passed', 'scope': 'retained_real_cli_historical_core_explanation_only', 'full_bundle_explanation_passed': False, 'current_target_market_report_passed': False, 'new_provider_calls': 0, 'production_writes': 0, 'formal_publication': False, 'source_inputs_unchanged': True, 'source_inputs': before_hashes, 'source_database_unchanged': True, 'original_report_body_unchanged': True, 'retained_real_attempt_unchanged': True, 'output_hash_reconstructed_exactly': expected_hash, 'paragraphs_reviewed': len(sections), 'public_review_method': 'ReportRepository.record_explanation_review', 'review': review, 'copied_database': str(copy), 'copied_database_sha256': sha(copy), 'elapsed_seconds': time.monotonic() - started}
    RECEIPT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: out[k] for k in ('state', 'result', 'scope', 'new_provider_calls', 'paragraphs_reviewed', 'source_inputs_unchanged', 'elapsed_seconds')}))


if __name__ == '__main__':
    main()

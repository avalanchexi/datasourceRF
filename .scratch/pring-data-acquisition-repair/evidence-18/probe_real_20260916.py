"""Real CLI diagnostic restricted to historical core states; never a current market report."""
import json
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from pring_cycle.reports import CliReportAdapter, EvidenceBundle, ReportRepository, ReportService

folder=Path(__file__).resolve().parent
source=json.loads((folder/'frozen-bundle.json').read_bytes())
assets=[{k:a[k] for k in ('asset','metric_id','state','latest_business_date')}
        | {'evidence_id':a['observation_version_ids'][-1]}
        for a in source['structured_context']['change_reasons']['core_assets']]
bundle=EvidenceBundle.create(
    projection_set_id=source['projection_set_id'],target_business_date=source['target_business_date'],
    report_cutoff=datetime.fromisoformat(source['report_cutoff']),
    system_as_of=datetime.fromisoformat(source['system_as_of']),
    model_version_id=source['model_version_id'],trend_rule_version=source['trend_rule_version'],
    current_stage=source['current_stage'],stage_reason=source['stage_reason'],core_states=source['core_states'],
    allowed_evidence_ids=tuple(a['evidence_id'] for a in assets),
    allowed_governance_refs=tuple(source['allowed_governance_refs']),
    support=tuple(source['support']),
    counterevidence=tuple(source['counterevidence'])+('历史目录已被来源审查隔离；本段仅解释旧记录，不证明当前市场或新来源认证。',),
    governance_gaps=tuple(source['governance_gaps']),
    structured_context={'core_asset_facts':assets,'source_frozen_bundle_id':source['bundle_id'],
                        'explanation_scope':'仅历史三核心状态和治理限制；不解释被省略的宏观、库存或派生值。'},
)
mode=sys.argv[1]
assert mode in ('codex_cli','claude_code_cli')
root=Path('/home/tywin/.cache/pring-cycle/verification')/('repair-18-real-20260916b-'+mode)
assert not root.exists(), 'one actual attempt; a repeat needs a new explicit experiment'
root.mkdir(mode=0o700)
tempfile.tempdir=str(root)
reports=ReportRepository.create(root/'reports.sqlite3')
(folder/'real-20260916b-bundle.json').write_text(json.dumps(bundle.document(),ensure_ascii=False,indent=2)+'\n')
result=ReportService(reports,(CliReportAdapter(mode),)).generate(bundle,client_request_id='focused-'+mode)
snapshot=reports.get(result.report_snapshot_id)
out={'scope':'historical_core_explanation_only','full_bundle_explanation_passed':False,
     'production_writes':0,'formal_publication':False,'result':asdict(result),'snapshot':asdict(snapshot),
     'attempts':[asdict(a) for a in reports.attempts(result.report_snapshot_id)]}
(folder/('real-20260916b-'+mode+'.json')).write_text(json.dumps(out,ensure_ascii=False,default=str,indent=2)+'\n')
print(json.dumps({'status':result.status,'attempts':[asdict(a) for a in reports.attempts(result.report_snapshot_id)]},default=str))

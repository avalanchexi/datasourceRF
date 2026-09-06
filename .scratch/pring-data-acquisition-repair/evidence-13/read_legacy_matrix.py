"""Public repository read APIs; all counts explicitly describe legacy definitions."""
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC,datetime
from pathlib import Path
from pring_cycle.evidence import AsOfMode,EvidenceRepository
from pring_cycle.models import ModelRepository

ROOT=Path(__file__).resolve().parent
DB=Path('/home/tywin/.local/share/pring-cycle/pring-cycle.sqlite3')
audit=json.loads(Path('.scratch/pring-data-acquisition-audit/metric-inventory.json').read_text())
excluded={'CN_EQ_CSI300','CN_EQ_CSI500','CN_EQ_CSI1000','CN_EQ_ADV_DEC','CN_EQ_AD_RATIO','CN_EQ_NEW_HIGH_LOW_120','CN_EQ_ABOVE_MA120','CN_EQ_ADV_AMOUNT_SHARE','CN_MARGIN_BALANCE','CN_INDEX_VALUATION','CN_BOND_FULL_PRICE_CNY030','CN_BOND_10Y_930916','CN_COMMODITY_BROAD_NHCI','CN_COMMODITY_EX_HOG_BASKET','CN_COMMODITY_SLEEVE_CONTRIBUTION'}
metrics=[m for m in audit['metrics'] if m['priority']=='P1' and m['metric_id'] not in excluded]
assert len(metrics)==27
now=datetime.now(UTC); cutoff=datetime.fromisoformat('2026-08-28T23:59:59+08:00')
repo=EvidenceRepository(DB); modelrepo=ModelRepository(DB); active=modelrepo.active(); manifest=modelrepo.manifest(active.model_version_id)
matrix=[]
for m in metrics:
    result={'metric_id':m['metric_id'],'frozen_v3_definition':m['frozen_v3_definition'],'historical_certification_package_ids':m['historical_certification_packages'],'audit_definition_versions':m['source_claim_versions'],'legacy_queries':{},'fresh_certification_granted':False,'candidate_model_adoption':'not_performed'}
    for label,mode,asof in (('public_at_target',AsOfMode.PUBLIC,cutoff),('system_at_target',AsOfMode.SYSTEM,cutoff),('system_at_research',AsOfMode.SYSTEM,now)):
        points=repo.metric_series(m['metric_id'],mode=mode,as_of=asof,definition_version='metric-catalog-v0003')
        points=tuple(p for p in points if p.period_end<='2026-08-28' or (m['metric_id']=='CN_LPR_1Y_5Y' and p.period_start<='2026-08-28'))
        latest=max((p.period_end for p in points),default=None)
        result['legacy_queries'][label]={'mode':mode.value,'as_of':asof.isoformat(),'point_count':len(points),'period_count':len({p.period_end for p in points}),'first_period':min((p.period_end for p in points),default=None),'last_period':latest,'dimension_members':len({json.dumps(p.dimensions,sort_keys=True) for p in points}),'selection_status_counts':dict(Counter(str(p.selection_status) for p in points)),'latest_sample':[asdict(p) for p in points if p.period_end==latest][:12]}
    matrix.append(result)
out={'read_at':now.isoformat(),'network_requests':0,'database_mutation_requested':False,'method':'ModelRepository.active/manifest and EvidenceRepository.metric_series only','meaning':'Legacy catalog read results are not re-certified PUBLIC results or candidate-model adoption. Derived-only values do not appear in source-series reads.','target_business_date':'2026-08-28','active_model':asdict(active),'manifest':manifest,'metric_count':len(matrix),'metrics':matrix,'audit_source_sha256':hashlib.sha256(Path('.scratch/pring-data-acquisition-audit/metric-inventory.json').read_bytes()).hexdigest()}
(ROOT/'legacy-read-matrix.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({'active_model':active.model_version_id,'metrics':[{k:r[k] for k in ('metric_id','legacy_queries')} for r in matrix]},ensure_ascii=False,default=str)[:1200])

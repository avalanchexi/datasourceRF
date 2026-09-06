"""Read existing model/evidence APIs for 13 P2; never acquire into or mutate runtime DB."""
import hashlib,json
from collections import Counter
from dataclasses import asdict
from datetime import UTC,datetime
from pathlib import Path
from pring_cycle.evidence import AsOfMode,EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.context_projection import build_context_projection

ROOT=Path(__file__).resolve().parent
DB=Path('/home/tywin/.local/share/pring-cycle/pring-cycle.sqlite3')
audit=json.loads(Path('.scratch/pring-data-acquisition-audit/metric-inventory.json').read_text())
metrics=[m for m in audit['metrics'] if m['priority']=='P2'];assert len(metrics)==13
now=datetime.now(UTC);cutoff=datetime.fromisoformat('2026-08-28T23:59:59+08:00')
repo=EvidenceRepository(DB);models=ModelRepository(DB);active=models.active();manifest=models.manifest(active.model_version_id)
matrix=[]
for m in metrics:
    item={'metric_id':m['metric_id'],'audit_definition':m['frozen_v3_definition'],'historical_source_claim_count':m['source_claim_counts']['source_claim_count'],'historical_derived_count':m['derived_observation_count'],'historical_certification_packages':m['historical_certification_packages'],'queries':{},'new_certification':False}
    for label,mode,asof,target in [('public_at_0828',AsOfMode.PUBLIC,cutoff,'2026-08-28'),('system_at_0828',AsOfMode.SYSTEM,cutoff,'2026-08-28'),('system_at_research',AsOfMode.SYSTEM,now,'2026-09-04')]:
        points=tuple(p for p in repo.metric_series(m['metric_id'],mode=mode,as_of=asof,definition_version='metric-catalog-v0003') if p.period_end<=target)
        latest=max((p.period_end for p in points),default=None)
        item['queries'][label]={'as_of':asof.isoformat(),'target_business_date':target,'point_count':len(points),'period_count':len({p.period_end for p in points}),'first_period':min((p.period_end for p in points),default=None),'last_period':latest,'selection_status_counts':dict(Counter(p.selection_status for p in points)),'latest_rows':[asdict(p) for p in points if p.period_end==latest]}
    matrix.append(item)
projection=build_context_projection(repo,as_of=now,model_manifest=manifest,target_business_date='2026-09-04',visible_evidence_start='2026-03-09',as_of_mode=AsOfMode.SYSTEM,persist_derived=False)
out={'read_at':now.isoformat(),'network_requests':0,'database_mutation_requested':False,'persist_derived':False,'active_model':asdict(active),'manifest':manifest,'metric_count':13,'metrics':matrix,'p2_projection':projection.macro['international_context'],'projection_warnings':projection.warnings,'source_audit_sha256':hashlib.sha256(Path('.scratch/pring-data-acquisition-audit/metric-inventory.json').read_bytes()).hexdigest(),'scope':'Legacy catalog observations and read-only candidate diagnostics only, not new source certification or formal publication.'}
(ROOT/'p2-read-matrix.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({'matrix':[{k:m[k] for k in ('metric_id','historical_source_claim_count','historical_derived_count')} for m in matrix],'projection':[(r['metric_id'],r['status'],r.get('period'),r.get('value')) for r in out['p2_projection']]},ensure_ascii=False,default=str))

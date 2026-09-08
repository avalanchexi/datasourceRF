from pathlib import Path
from datetime import datetime
from dataclasses import asdict
import json
from pring_cycle.official_context import parse_official_context_document
r=Path(__file__).resolve().parent/'evidence-search-preexperiment-20260908-n4-v1'
j=json.loads((r/'result.json').read_bytes())
d=next(x for x in j['documents'] if x['arm_id']=='rrr-pbc-notice-20250515:tavily' and x['candidate_index']==0)
p=parse_official_context_document((r/d['receipt']['raw_hash']).read_bytes(),family='pbc_rrr_notice',source_url=d['url'],expected_period='2025-05',fetched_at=datetime.fromisoformat(d['receipt']['received_at']))
assert len(p.scalars)==2
assert sorted(x.value for x in p.scalars)==[-5.0,-0.5]
assert all(x.period_start==x.period_end=='2025-05-15' for x in p.scalars)
assert p.release_at.isoformat()=='2025-05-07T10:00:00+08:00'
with (r/'rrr-public-parser-verification.json').open('x',encoding='utf-8') as h:
 json.dump({'actual_network_requests':0,'new_claims':0,'new_certifications':0,'parsed':asdict(p),'acquisition_id':d['receipt']['acquisition_id'],'raw_hash':d['receipt']['raw_hash']},h,ensure_ascii=False,indent=2,default=str)
 h.write('\n')
print(json.dumps({'values':[x.value for x in p.scalars],'release_at':p.release_at.isoformat(),'effective_date':p.scalars[0].period_start}))

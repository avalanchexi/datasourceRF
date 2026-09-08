from pathlib import Path
import json
from urllib.parse import urlsplit
from pring_cycle.acquisition import AcquisitionRepository
r=Path(__file__).resolve().parent/'evidence-search-preexperiment-20260908-n4-v1'
f=json.loads((r/'frozen.json').read_bytes())
v=json.loads((r/'independent-receipt-verification.json').read_bytes())
a=AcquisitionRepository(Path(f['runtime']['database']),Path(f['runtime']['artifacts']))
rows=[]
for record in v['records']:
 doc=json.loads(a.read_content(record['acquisition_id'],'raw'))
 for index,item in enumerate(doc['results'][:3]):
  url=item.get('url')
  parsed=urlsplit(url) if isinstance(url,str) else None
  reason=('missing_url' if parsed is None else 'url_too_long' if len(url)>2048
          else 'https_required' if parsed.scheme!='https' else 'hostname_required' if not parsed.hostname
          else 'userinfo_forbidden' if parsed.username or parsed.password else 'accepted_as_unverified_candidate')
  rows.append({'sample_id':record['sample_id'],'provider':record['provider'],'acquisition_id':record['acquisition_id'],
   'raw_hash':record['raw_hash'],'provider_result_index':index,'url':url,'adapter_screening':reason})
with (r/'provider-candidate-screening.json').open('x',encoding='utf-8') as h:
 json.dump({'network_requests':0,'model_evaluation':'not_evaluated','results':rows},h,ensure_ascii=False,indent=2)
 h.write('\n')
print(json.dumps([x for x in rows if x['sample_id'].startswith('pp-')]))

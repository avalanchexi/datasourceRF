"""Read-only native receipt/hash verification for the completed real pilot."""
from pathlib import Path
from dataclasses import asdict
import json, hashlib, sqlite3
from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.models import ModelRepository
from pring_cycle.retrieval_ledger import RetrievalLedger
r=Path(__file__).resolve().parent/'evidence-search-preexperiment-20260908-n4-v1'
f=json.loads((r/'frozen.json').read_bytes())
p=json.loads((r/'plan.json').read_bytes())
result=json.loads((r/'result.json').read_bytes())
assert hashlib.sha256((r/'plan.json').read_bytes()).hexdigest()==f['plan_sha256']
assert hashlib.sha256((r.parent/'run-search-preexperiment.py').read_bytes()).hexdigest()==f['executor_sha256']
db=Path(f['runtime']['database'])
a=AcquisitionRepository(db,Path(f['runtime']['artifacts']))
l=RetrievalLedger(db)
records=[]
for sample in p['samples']:
 run_id=json.loads((r/(sample['sample_id']+'-run.json')).read_bytes())['run_id']
 snapshot=l.for_run(run_id)
 assert snapshot==json.loads((r/(sample['sample_id']+'-ledger.json')).read_bytes())
 assert len(snapshot['requests'])==2 and not snapshot['candidate_validations']
 assert {q['query_text'] for q in snapshot['queries']}=={sample['query']}
 for request in snapshot['requests']:
  receipt=a.get(request['acquisition_id'])
  raw=a.read_content(receipt.acquisition_id,'raw')
  assert hashlib.sha256(raw).hexdigest()==request['raw_hash']==receipt.raw_hash
  parsed=json.loads(raw)
  records.append({'sample_id':sample['sample_id'],'provider':request['channel'],
   'acquisition_id':receipt.acquisition_id,'raw_hash':receipt.raw_hash,'bytes':len(raw),
   'parsed_json':True,'cost':request['cost'],'raw_expires_at':request['raw_expires_at'],
   'provider_result_count':len(parsed.get('results',[]))})
for doc in result['documents']:
 for identity in doc.get('acquisition_ids',[]):
  receipt=a.get(identity)
  assert asdict(receipt)=={k: ( __import__('datetime').datetime.fromisoformat(v) if k.endswith('_at') and v else v) for k,v in doc['receipt'].items()}
  if receipt.raw_hash:
   raw=a.read_content(identity,'raw')
   assert raw==(r/receipt.raw_hash).read_bytes()
models=ModelRepository(db)
assert len(models.list_versions())==3 and not models.activation_history()
with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
 tables={x[0] for x in c.execute("select name from sqlite_master where type='table'")}
 counts={name:c.execute('select count(*) from '+name).fetchone()[0] for name in ['source_claim','source_certification','model_acceptance','model_replay','active_model'] if name in tables}
 assert all(v==0 for v in counts.values())
report={'search_receipts_verified':len(records),'records':records,'default_runtime_writes':0,
 'isolated_empty_tables':counts,'isolated_bookkeeping_models':3,'activation_history':[],
 'model_qualification_evaluated':False,'model_usable_completion_rate':None,
 'plan_sha256':f['plan_sha256'],'executor_sha256':f['executor_sha256']}
with (r/'independent-receipt-verification.json').open('x',encoding='utf-8') as h:
 json.dump(report,h,ensure_ascii=False,indent=2)
 h.write('\n')
print(json.dumps({'search_receipts_verified':len(records),'empty_tables':counts}))

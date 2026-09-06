"""Verify every retained response/import byte and local Markdown link without network."""
import hashlib,json,re
from collections import Counter
from datetime import UTC,datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
receipts=json.loads((ROOT/'receipts.json').read_text())
imports=json.loads((ROOT/'imports.json').read_text())
verified=[]
for kind,records in [('http',receipts),('prior_cas',imports)]:
    for r in records:
        if 'sha256' not in r:continue
        p=ROOT/r['local_file'];raw=p.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['sha256'],p
        assert len(raw)==r['bytes'],p
        verified.append({'kind':kind,**r})
rawfiles=[p for p in ROOT.iterdir() if re.fullmatch('[a-f0-9]{64}',p.name)]
assert {p.name for p in rawfiles}=={r['sha256'] for r in verified}
report=ROOT.parent/'research-13.md'
local=[]
for label,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',report.read_text(encoding='utf-8')):
    if target.startswith(('https://','http://','#')):continue
    resolved=(report.parent/target.split('#')[0]).resolve()
    local.append({'label':label,'target':target,'exists':resolved.exists() or resolved==(ROOT/'artifact-verification.json').resolve()})
assert all(x['exists'] for x in local),[x for x in local if not x['exists']]
checks=json.loads((ROOT/'research-checks.json').read_text())
assert all(x['matches'] for x in checks['shibor'])
assert sum(x['matched'] for x in checks['warrants'])==134
assert sum(x['mismatched'] for x in checks['warrants'])==0
matrix=json.loads((ROOT/'legacy-read-matrix.json').read_text())
assert len(matrix['metrics'])==27
assert all(x['legacy_queries']['system_at_target']['point_count']==0 for x in matrix['metrics'])
ci=checks['credit_impulse_from_official_raw_records']
assert abs(float(ci['expected_percentage_points'])-ci['legacy_projection_value'])<1e-12
hist=json.loads((ROOT/'history-verification.json').read_text())
assert hist['raw_record_count']==270
assert len(hist['results'])==288
assert all(x['status']=='parsed' for x in hist['results'])
out={'verified_at':datetime.now(UTC).isoformat(),'network_requests_in_verification':0,'public_get_requests':len(receipts),'http_status_counts':dict(Counter(str(x.get('status',x.get('error_type'))) for x in receipts)),'import_records':len(imports),'unique_original_files':len(rawfiles),'original_bytes':sum(p.stat().st_size for p in rawfiles),'original_records':verified,'local_links_checked':len(local),'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'file_checks':[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(ROOT.iterdir()) if p.is_file() and p.name not in ('artifact-verification.json','inspection-run.txt')],'excluded_temporary_outputs':['__pycache__/','inspection-run.txt'],'claims':'Hash and arithmetic verification only; no source certification, model activation or candidate acceptance.'}
(ROOT/'artifact-verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ('original_records','file_checks')},ensure_ascii=False,indent=2))

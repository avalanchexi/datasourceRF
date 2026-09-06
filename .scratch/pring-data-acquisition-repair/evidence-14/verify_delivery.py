"""Verify bytes and report links, then emit the exact bounded handoff manifest."""
import hashlib,json,re
from collections import Counter
from datetime import UTC,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
REPORT=ROOT.parent/'research-14.md'
receipts=json.loads((ROOT/'receipts.json').read_text(encoding='utf-8'))
imports=json.loads((ROOT/'imports.json').read_text(encoding='utf-8'))
raw_records=receipts+imports
checks=[]
for r in raw_records:
    if not r.get('sha256'):continue
    p=ROOT/r['local_file'];raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==r['sha256'],p
    assert len(raw)==r['bytes'],p
    assert not r.get('truncated'),p
    checks.append({'sha256':r['sha256'],'bytes':len(raw),'url':r.get('url'),'status':r.get('status'),'verified':True})
unique={r['sha256']:r['bytes'] for r in checks}
rawnames={p.name for p in ROOT.iterdir() if re.fullmatch('[a-f0-9]{64}',p.name)}
assert rawnames==set(unique)
lines=['# 票14原件索引','','所有GET精确起止时间/响应头见 `receipts.json`；本表原件与HTTP错误均保存。原件SHA证明字节完整，不授予数据来源认证。','','| # | URL/来源 | HTTP | 字节 | 取得/复制时间 UTC | SHA256原件 |','|---:|---|---:|---:|---|---|']
for i,r in enumerate(raw_records,1):
    url=r.get('url','https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html')
    h=r.get('sha256');link=f'[{h}]({h})' if h else '无响应原件'
    lines.append(f"| {i} | {url} | {r.get('status','CAS复制')} | {r.get('bytes','—')} | {r.get('received_at',r.get('imported_at'))} | {link} |")
lines+=['',f'GET {len(receipts)}次；唯一原件{len(unique)}份，总字节{sum(unique.values()):,}；包含HTTP失败体，不能全部计为有效数据。','']
(ROOT/'raw-index.md').write_text('\n'.join(lines),encoding='utf-8')
local_links=[]
for doc in (REPORT,ROOT/'raw-index.md'):
    for target in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
        if target.startswith(('https://','http://','#')):continue
        p=(doc.parent/target.split('#')[0]).resolve()
        assert p.exists() or p.name in ('delivery-verification.json','delivery-files.txt'),(doc,target)
        local_links.append({'document':str(doc.relative_to(REPO)).replace('\\','/'),'target':target,'exists':True})
matrix=json.loads((ROOT/'availability-matrix.json').read_text(encoding='utf-8'));assert matrix['count']==13
sample=json.loads((ROOT/'sample-comparison.json').read_text(encoding='utf-8'))
assert all(r['matches'] for r in sample['treasury']['source_vs_repository'])
assert sum(r.get('matches_official_quarter') is False for r in sample['gdp']['comparisons'])==3
assert sum(r.get('matches_official_ytd') is True for r in sample['gdp']['comparisons'])==4
parsed=json.loads((ROOT/'pure-parser-results.json').read_text(encoding='utf-8'))
assert parsed['cases'][0]['parsed']['scalars'][0]['value']==6.7787
assert parsed['cases'][0]['parsed']['public_available_at']=='2026-09-04 09:25:17+08:00'
assert len(parsed['cases'][2]['parsed']['scalars'])==8
from pypdf import PdfReader
pbc_pdf=PdfReader(ROOT/'3a0eab7fc9d21b0c28449d1b557a5fbb8b615650f8cba8eb3f3bea37cf950581')
pages=[i+1 for i,p in enumerate(pbc_pdf.pages) if '16:30' in (p.extract_text() or '')]
names=[REPORT]+[p for p in ROOT.iterdir() if p.is_file() and not p.name.endswith('-run.txt')]
for name in ('delivery-verification.json','delivery-files.txt'):
    p=ROOT/name
    if p not in names:names.append(p)
paths=sorted(str(p.relative_to(REPO)).replace('\\','/') for p in names)
(ROOT/'delivery-files.txt').write_text('\n'.join(paths)+'\n',encoding='utf-8')
files=[]
for name in paths:
    p=REPO/name
    if p.name=='delivery-verification.json':continue
    b=p.read_bytes();files.append({'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
result={'verified_at':datetime.now(UTC).isoformat(),'read_only_research':True,'get_attempt_count':len(receipts),'get_status_counts':dict(Counter(str(r.get('status','no_response')) for r in receipts)),'get_success_ratio':sum(r.get('status')==200 for r in receipts)/len(receipts),'cas_import_count':len(imports),'unique_raw_count':len(unique),'unique_raw_bytes':sum(unique.values()),'raw_receipt_checks':checks,'report_local_link_count':len(local_links),'report_local_links':local_links,'metric_count':13,'pbc_schedule_pdf_pages_1_based':pages,'delivery_path_count':len(paths),'files':files,'verification_file_self_hash_excluded':True,'new_certifications':0,'production_mutations_requested':0,'tavily_calls':0,'exa_calls':0}
(ROOT/'delivery-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('files','raw_receipt_checks','report_local_links')},ensure_ascii=False,indent=2))

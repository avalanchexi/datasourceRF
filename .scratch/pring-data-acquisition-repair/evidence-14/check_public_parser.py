"""Call production pure parser on preserved documents; no ingestion/network."""
import hashlib,json
from dataclasses import asdict
from datetime import UTC,datetime
from pathlib import Path
from pring_cycle.official_context import parse_official_context_document
ROOT=Path(__file__).resolve().parent
cases=[('pbc_usdcny_central_parity','2026-09-04','https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/2026090409004494582/index.html','a87d0e4db691a1a8cfe6bfef8217b616e59140daa68f92dfb2acefe4417f70aa'),('nbs_gdp','2026Q2','https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html','60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915')]
cases.append(('nbs_gdp','2026-Q2',cases[1][2],cases[1][3]))
out=[]
for family,period,url,h in cases:
    raw=(ROOT/h).read_bytes();assert hashlib.sha256(raw).hexdigest()==h
    try:r=asdict(parse_official_context_document(raw,family=family,source_url=url,expected_period=period,fetched_at=datetime.now(UTC)))
    except Exception as e:r={'error_type':type(e).__name__,'error':str(e)}
    out.append({'family':family,'period':period,'url':url,'sha256':h,'parsed':r,'new_certification':False})
(ROOT/'pure-parser-results.json').write_text(json.dumps({'network_requests':0,'production_mutations':0,'cases':out},ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps(out,ensure_ascii=False,default=str))

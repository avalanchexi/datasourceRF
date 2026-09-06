"""Independent raw sample checks and old-manifest projection, explicitly non-persistent."""
import hashlib
import inspect
import json
from dataclasses import asdict
from datetime import UTC,datetime
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode,EvidenceRepository
from pring_cycle.models import ModelRepository
import pring_cycle.official_context as context_parser
import pring_cycle.official_lpr as lpr_parser

ROOT=Path(__file__).resolve().parent
DB=Path('/home/tywin/.local/share/pring-cycle/pring-cycle.sqlite3')
now=datetime.now(UTC); cutoff=datetime.fromisoformat('2026-08-28T23:59:59+08:00')
repo=EvidenceRepository(DB); mr=ModelRepository(DB); active=mr.active(); manifest=mr.manifest(active.model_version_id)
class Rows(HTMLParser):
    def __init__(self): super().__init__();self.rows=[];self.row=[];self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:self.row.append(''.join(self.cell).strip());self.cell=None
        if tag=='tr':self.rows.append(self.row)

raw=(ROOT/'aa7493a24425f6f95f9743bc8e53725deb0e2cbba10857d97443758eedef4e39').read_bytes()
p=Rows();p.feed(raw.decode('utf-8'))
products={}; current=None
for row in p.rows:
    if len(row)==2 and row[1].startswith('单位：'):
        current=row[0];products[current]={'unit':row[1][3:],'rows':[]}
    elif current and len(row)>=3:
        try: vol=Decimal(row[-2]);chg=Decimal(row[-1])
        except Exception:continue
        products[current]['rows'].append({'labels':row[:-2],'value':str(vol),'change':str(chg)})
points=repo.metric_series('CN_FUTURES_WARRANTS',mode=AsOfMode.SYSTEM,as_of=now,definition_version='metric-catalog-v0003')
latest=[asdict(x) for x in points if x.period_end=='2026-08-28']
shibor=json.loads((ROOT/'365f18b1a160570e6d0762040bf6af670379be2946bec553593d2cbae3881f62').read_text())['records'][0]
old=json.loads((ROOT/'legacy-read-matrix.json').read_text())
shibor_points=next(x for x in old['metrics'] if x['metric_id']=='CN_SHIBOR_ON_1W_3M')['legacy_queries']['system_at_research']['latest_sample']
checks=[]
for tenor,field in [('overnight','ON'),('1w','1W'),('3m','3M')]:
    point=next(x for x in shibor_points if x['dimensions']['tenor']==tenor)
    checks.append({'name':'official_shibor_vs_legacy_'+tenor,'expected_official':shibor[field],'legacy_value':point['selected_value'],'matches':Decimal(shibor[field])==Decimal(str(point['selected_value'])),'official_raw':'365f18b1a160570e6d0762040bf6af670379be2946bec553593d2cbae3881f62','legacy_claim_id':point['selected_claim_id'],'historical_release_time_proved':False})
comparisons=[]
for symbol,product in [('CU','铜'),('RB','螺纹钢'),('RU','天然橡胶'),('SP','纸浆'),('SC','原油')]:
    source=products.get(product)
    observed=[x for x in latest if x['dimensions']['symbol']==symbol and x['dimensions']['measure']=='registered_receipts']
    matches=[]
    if source:
        for row in source['rows']:
            if len(row['labels'])!=1 or row['labels'][0] in ('总计','合计','保税商品总计','完税商品总计'):continue
            candidates=[x for x in observed if x['dimensions']['warehouse']==row['labels'][0]]
            if len(candidates)==1:
                point=candidates[0]
                matches.append({'warehouse':row['labels'][0],'official_value':row['value'],'official_unit':source['unit'],'legacy_value':point['selected_value'],'legacy_unit':point['claims'][0]['unit'],'matches_value':Decimal(row['value'])==Decimal(str(point['selected_value'])),'legacy_claim_id':point['selected_claim_id']})
    comparisons.append({'symbol':symbol,'product':product,'official_found':source is not None,'unit':source['unit'] if source else None,'official_total_rows':[r for r in source['rows'] if r['labels']==['总计']] if source else [],'legacy_rows':len(observed),'exact_label_comparisons':matches,'historical_release_time_proved':False})
projection=build_context_projection(repo,as_of=cutoff,model_manifest=manifest,target_business_date='2026-08-28',visible_evidence_start='2026-03-09',as_of_mode=AsOfMode.PUBLIC,persist_derived=False)
out={'read_at':now.isoformat(),'network_requests':0,'database_mutation_requested':False,'persist_derived':False,'old_model_id':active.model_version_id,'candidate_model_adoption':'not_performed','shibor_checks':checks,'official_warrant_tables':products,'warrant_comparisons':comparisons,'legacy_warrants_latest':latest,'legacy_projection':asdict(projection),'parser_modules':[{'module':m.__name__,'actual_file':inspect.getfile(m),'sha256':hashlib.sha256(Path(inspect.getfile(m)).read_bytes()).hexdigest()} for m in (context_parser,lpr_parser)]}
(ROOT/'readonly-checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({'shibor':checks,'warrants':[{k:v for k,v in x.items() if k!='exact_label_comparisons'}|{'matched':sum(y['matches_value'] for y in x['exact_label_comparisons']),'mismatch':sum(not y['matches_value'] for y in x['exact_label_comparisons'])} for x in comparisons],'projection_warnings':projection.warnings},ensure_ascii=False,default=str))

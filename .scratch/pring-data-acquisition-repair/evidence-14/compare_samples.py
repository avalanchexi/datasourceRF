"""Recompute source samples and local coverage without network/production mutation."""
import csv,hashlib,json,re
from datetime import datetime,timedelta
from decimal import Decimal
from html import unescape
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TREASURY='54a2b1462c7a2116201b45eaf2dfdfe8fe3654cfd62fe46b6c2c09439c252330'
VIX='9258a25814fb936e7df32a96bcf3914fdbf342afb33cdf8759cdfbc8064ddb72'
BRENT='b078a362332a3d6b34ae2a5dc5a91b98ddfacc7979410b32081f07e9dadc243e'
WTI='7da3e5b6632942bfedf02642fde22867d24bb0cf6477eff5ac9e5f9be4d92497'
NBS='60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915'
def raw(h):
    b=(ROOT/h).read_bytes();assert hashlib.sha256(b).hexdigest()==h
    return b.decode('utf-8')
def clean(v):return re.sub(r'\s+',' ',unescape(re.sub('<[^>]*>',' ',v))).strip()
def rows(h):
    return [[clean(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>',tr,re.S|re.I)] for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>',raw(h),re.S|re.I)]
def coverage(data):
    keys=sorted(data)
    window=[k for k in keys if '2026-03-09'<=k<='2026-09-04']
    return {'row_count':len(keys),'first_period':keys[0],'latest_period':keys[-1],'window_20260309_to_20260904_rows':len(window),'window_first':min(window),'window_last':max(window),'note':'Source-local business-date rows; this is not a certified Chinese 120-day replay or proof of original historical publication.'}
treasury={}
for rr in rows(TREASURY):
    if len(rr)==26 and re.fullmatch(r'\d\d/\d\d/2026',rr[0]):
        key=datetime.strptime(rr[0],'%m/%d/%Y').date().isoformat()
        treasury[key]={'2 Yr':rr[-7],'10 Yr':rr[-3],'raw_cells':rr}
assert treasury
vix={datetime.strptime(r['DATE'],'%m/%d/%Y').date().isoformat():r for r in csv.DictReader(raw(VIX).splitlines())}
eia={}
for h,key in [(BRENT,'RBRTE'),(WTI,'RWTC')]:
    parsed={}
    for rr in rows(h):
        if not rr:continue
        m=re.fullmatch(r'(\d{4}) ([A-Z][a-z]{2})-\s*(\d{1,2}) to [A-Z][a-z]{2}-\s*\d{1,2}',rr[0])
        if not m:continue
        monday=datetime.strptime(' '.join(m.groups()),'%Y %b %d').date()
        for i,cell in enumerate(rr[1:6]):
            if re.fullmatch(r'-?\d+(?:\.\d+)?',cell):parsed[(monday+timedelta(days=i)).isoformat()]=cell
    assert parsed
    eia[key]={'sha256':h,'coverage':coverage(parsed),'samples':{k:parsed[k] for k in ('2026-08-28',sorted(parsed)[-1])},'release_date':re.search(r'Release Date: (\d+/\d+/\d+)',raw(h)).group(1),'next_release_date':re.search(r'Next Release Date: (\d+/\d+/\d+)',raw(h)).group(1)}
matrix=json.loads((ROOT/'p2-read-matrix.json').read_text(encoding='utf-8'))
gdp=next(m for m in matrix['metrics'] if m['metric_id']=='CN_GDP')
gdp_sample=[]
official_gdp={rr[0]:rr[1:] for rr in rows(NBS) if len(rr)==5 and rr[0] in ('GDP','第一产业','第二产业','第三产业')}
assert len(official_gdp)==4,official_gdp
label={'total':'GDP','primary':'第一产业','secondary':'第二产业','tertiary':'第三产业'}
for p in gdp['queries']['system_at_research']['latest_rows']:
    d=p['dimensions'];nbs=official_gdp[label[d['aggregate']]]
    ts=next(c for c in p['claims'] if c['provider']=='tushare')
    n=next(c for c in p['claims'] if c['provider']=='国家统计局')
    sample={'dimensions':d,'period':'2026-06-30','tushare_value':ts['value'],'official_selected_field_value':n['value'],'local_selection_status':p['selection_status'],'official_row':nbs,'source_reference':ts['source_reference']}
    if d['measure']=='real_quarter_yoy':
        sample.update(official_quarter_yoy=nbs[2],official_ytd_yoy=nbs[3],matches_official_quarter=Decimal(str(ts['value']))==Decimal(nbs[2]),matches_official_ytd=Decimal(str(ts['value']))==Decimal(nbs[3]))
    else:sample['difference_hundred_million_cny']=str(Decimal(str(ts['value']))-Decimal(nbs[1]))
    gdp_sample.append(sample)
ustchecks=[]
for metric,col in [('UST2Y_NOMINAL_YIELD','2 Yr'),('UST10Y_NOMINAL_YIELD','10 Yr')]:
    m=next(m for m in matrix['metrics'] if m['metric_id']==metric)
    latest=m['queries']['system_at_research']['latest_rows']
    for p in latest:
        official=treasury[p['period_end']][col]
        ustchecks.append({'metric_id':metric,'period':p['period_end'],'local':p['selected_value'],'official':official,'matches':Decimal(str(p['selected_value']))==Decimal(official)})
samples={day:{'2 Yr':treasury[day]['2 Yr'],'10 Yr':treasury[day]['10 Yr'],'spread_bp':str((Decimal(treasury[day]['10 Yr'])-Decimal(treasury[day]['2 Yr']))*100)} for day in ('2026-08-28','2026-09-04')}
out={'network_requests':0,'production_mutations':0,'treasury':{'sha256':TREASURY,'column_count':26,'columns_index_zero_based':{'date':0,'2 Yr':19,'10 Yr':23},'coverage':coverage(treasury),'samples':samples,'source_vs_repository':ustchecks},'vix':{'sha256':VIX,'fieldnames':['DATE','OPEN','HIGH','LOW','CLOSE'],'coverage':coverage(vix),'samples':{k:vix[k] for k in ('2026-08-28','2026-09-04')}},'eia':eia,'gdp':{'sha256':NBS,'official_row_columns':['nominal_quarter_level','nominal_ytd_level','real_quarter_yoy','real_ytd_yoy'],'comparisons':gdp_sample},'repository_metrics':[{ 'metric_id':m['metric_id'],'queries':{k:{kk:vv for kk,vv in q.items() if kk!='latest_rows'} for k,q in m['queries'].items()}} for m in matrix['metrics']]}
(ROOT/'sample-comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='repository_metrics'},ensure_ascii=False,indent=2))

"""Research-only independent arithmetic from retained official parse records."""
import hashlib,json
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parent
h=json.loads((ROOT/'history-verification.json').read_text())
j=json.loads((ROOT/'readonly-checks.json').read_text())
latest=j['legacy_warrants_latest']; products=j['official_warrant_tables']
comparisons=[]
for symbol,names in [('CU',['铜']),('RB',['螺纹钢(仓库)','螺纹钢(厂库)']),('RU',['天然橡胶']),('SP',['纸浆(仓库)','纸浆(厂库)']),('SC',['中质含硫原油'])]:
    observed=[p for p in latest if p['dimensions']['symbol']==symbol and p['dimensions']['measure']=='registered_receipts']
    matches=[]; tables=[]
    for name in names:
        source=products[name]; tables.append({'name':name,'unit':source['unit'],'totals':[r for r in source['rows'] if r['labels']==['总计']]})
        for row in source['rows']:
            if any(label in ('总计','合计','保税商品总计','完税商品总计') for label in row['labels']):continue
            candidates=[p for p in observed if p['dimensions']['warehouse'] in row['labels']]
            if len(candidates)!=1:continue
            point=candidates[0]
            matches.append({'product':name,'labels':row['labels'],'official_value':row['value'],'official_unit':source['unit'],'legacy_value':point['selected_value'],'legacy_unit':next(c['unit'] for c in point['claims'] if c['claim_id']==point['selected_claim_id']),'matches_value':Decimal(row['value'])==Decimal(str(point['selected_value'])),'claim_id':point['selected_claim_id']})
    comparisons.append({'symbol':symbol,'official_tables':tables,'legacy_rows':len(observed),'comparisons':matches,'matched':sum(x['matches_value'] for x in matches),'mismatched':sum(not x['matches_value'] for x in matches),'scope':'Exact warehouse labels only; no guessed alias or aggregated-unit conversion; not certification.'})

def scalar(metric,dimensions):
    selected={}
    for r in h['results']:
        if r['status']!='parsed':continue
        for s in r['parsed'].get('scalars',[]):
            if s['metric_id']==metric and s['dimensions']==dimensions:
                item={'period':r['period'],'value':str(s['value']),'raw_sha256':r['artifact_hash'],'release_at':r['parsed']['release_at']}
                if r['period'] not in selected or item['release_at']>selected[r['period']]['release_at']:selected[r['period']]=item
    return selected

sf=scalar('CN_SF_TOTAL',{'measure':'ytd_increment'})
gdp=scalar('CN_GDP',{'aggregate':'total','measure':'nominal_ytd_level'})
flows=[]
for period,s in sorted(sf.items()):
    y,m=map(int,period.split('-')); prev=f'{y}-{m-1:02}'
    if m==1:v=Decimal(s['value']); inputs=[s]
    elif prev in sf:v=Decimal(s['value'])-Decimal(sf[prev]['value']);inputs=[sf[prev],s]
    else:continue
    flows.append({'period':period,'value':str(v),'sources':inputs})
quarters=[]
for period,s in sorted(gdp.items()):
    y,q=period.split('-Q');q=int(q);prev=f'{y}-Q{q-1}'
    if q==1:v=Decimal(s['value']); inputs=[s]
    elif prev in gdp:v=Decimal(s['value'])-Decimal(gdp[prev]['value']);inputs=[gdp[prev],s]
    else:continue
    quarters.append({'period':period,'value':str(v),'sources':inputs})
lastflows=flows[-24:];lastquarters=quarters[-8:]
sf_prev=sum(Decimal(x['value']) for x in lastflows[:12]); sf_cur=sum(Decimal(x['value']) for x in lastflows[12:])
gdp_prev=sum(Decimal(x['value']) for x in lastquarters[:4]);gdp_cur=sum(Decimal(x['value']) for x in lastquarters[4:])
expected=(sf_cur/gdp_cur-sf_prev/gdp_prev)*100

def records(value):
    if isinstance(value,dict):
        yield value
        for v in value.values():yield from records(v)
    elif isinstance(value,list):
        for v in value:yield from records(v)

derived={}
for x in records(j['legacy_projection']):
    if x.get('metric_id') in ('CN_CREDIT_IMPULSE','CN_DR007_POLICY_SPREAD','CN_ORDER_INVENTORY_SPREAD','CN_PRODUCTION_ORDER_SPREAD') and 'value' in x:derived[x['metric_id']]=x
out={'meaning':'Human-review research aids, not candidate acceptance; source records were independently byte-verified but these arithmetic checks also depend on their existing parser field extraction. Hand expectations below are stated independently for future tests.','shibor':j['shibor_checks'],'warrants':comparisons,'credit_impulse_from_official_raw_records':{'formula':'100*(current12mSF/current4qGDP - prior12mSF/prior4qGDP)','monthly_inputs':lastflows,'quarterly_inputs':lastquarters,'current_sf':str(sf_cur),'previous_sf':str(sf_prev),'current_gdp':str(gdp_cur),'previous_gdp':str(gdp_prev),'expected_percentage_points':str(expected),'legacy_projection_value':derived.get('CN_CREDIT_IMPULSE',{}).get('value')},'legacy_projection_derived_rows':derived,'independent_hand_expectations':[{'case':'2026-07 PMI order minus finished goods inventory','inputs':[48.5,48.6],'expected':-0.1,'unit':'diffusion_index_points'},{'case':'2026-07 PMI production minus new orders','inputs':[49.9,48.5],'expected':1.4,'unit':'diffusion_index_points'},{'case':'2026-08-28 legacy DR007 minus official OMO7d rate; conditional on later DR certification','inputs_percent':[1.3859,1.4],'expected':-1.41,'unit':'basis_points'},{'case':'2026-07 official 7d reverse repo monthly inflow minus outflow','inputs_hundred_million_cny':[47395,49890],'expected':-2495,'unit':'hundred_million_cny'},{'case':'2026-07 M1 trillion to hundred million CNY','inputs':[115.46,10000],'expected':1154600,'unit':'hundred_million_cny'},{'case':'Synthetic annual ratio difference with equal GDP units','inputs':{'current12mSF':240,'previous12mSF':120,'current4qGDP':1200,'previous4qGDP':1000},'expected':8,'unit':'percentage_points','fixture_kind':'synthetic_not_live_evidence'}]}
(ROOT/'research-checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'warrants':[{k:v for k,v in x.items() if k not in ('comparisons','scope')} for x in comparisons],'credit':{k:v for k,v in out['credit_impulse_from_official_raw_records'].items() if k not in ('monthly_inputs','quarterly_inputs')},'derived':[(k,v.get('value')) for k,v in derived.items()]},ensure_ascii=False,indent=2))

"""Read-only verification of existing input CAS and current public receipts."""
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CAS=Path('/home/tywin/.local/share/pring-cycle/artifacts/sha256')
def read(digest):
    path=CAS/digest[:2]/digest
    raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==digest
    return raw
manifest=json.loads((ROOT/'dfa264f956d2c07def24190b0fda8dc8da6160b6c37000fe165c9cde9b834110').read_text())
receipts=manifest['receipts']
print('RECEIPT',json.dumps(receipts[0]))
print('DAY',json.dumps(manifest['days'][0]))
checks=[]; selected=[]
for receipt in receipts:
    digest=receipt['raw_sha256']; raw=read(digest)
    assert len(raw)==receipt['bytes']
    request=receipt['request']; data=json.loads(raw)['data']
    rows=[dict(zip(data['fields'],row)) for row in data['items']]
    checks.append({'sha256':digest,'bytes':len(raw),'api_name':request['api_name'],'row_count':len(rows)})
    day=request.get('params',{}).get('trade_date')
    for row in rows:
        code=row.get('ts_code')
        if code in ('688781.SH','600636.SH','600355.SH','002731.SZ','603159.SH','920078.BJ') and (request['api_name']=='stock_basic' or day in ('20260318','20260324','20260325','20260403','20260407','20260424','20260427','20260616','20260622','20260623','20260624','20260625','20260626','20260629','20260706','20260707')):
            selected.append({'request':request,'row':row,'sha256':digest})
normalized=[]; membership_changes=[]; previous=None; member_union=set(); member_days=quoted_days=suspended_days=unknown_amounts=0
for day in manifest['days']:
    raw=read(day['normalized_sha256']); parsed=json.loads(raw)
    normalized.append({'date':day['date'],'sha256':day['normalized_sha256'],'bytes':len(raw)})
    members={x[0] for x in parsed['listed_on']}; member_union.update(members)
    member_days+=len(members); quoted_days+=len(parsed['quotes']); suspended_days+=len(parsed['suspended_codes'])
    unknown_amounts+=sum(q['after_hours_amount'] is None for q in parsed['quotes'])
    if previous is not None and members!=previous:
        membership_changes.append({'date':day['date'],'entered':sorted(members-previous),'exited':sorted(previous-members)})
    previous=members
local=[]
for name in ('receipts.json','imports.json'):
    for row in json.loads((ROOT/name).read_text()):
        if 'sha256' not in row:continue
        raw=(ROOT/row['local_file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==row['sha256'] and len(raw)==row['bytes']
        local.append(row['sha256'])
out={'verified_at':datetime.now(UTC).isoformat(),'network_requests_this_verification':0,'active_database_modified':False,'source_certification_created':False,'existing_manifest_sha256':'dfa264f956d2c07def24190b0fda8dc8da6160b6c37000fe165c9cde9b834110','raw_receipts_verified':len(checks),'raw_bytes_verified':sum(x['bytes'] for x in checks),'raw_by_api':dict(Counter(x['api_name'] for x in checks)),'normalized_inputs_verified':len(normalized),'member_days':member_days,'quoted_member_days':quoted_days,'suspended_member_days':suspended_days,'unknown_after_hours_member_days':unknown_amounts,'unique_members':len(member_union),'membership_entry_count':sum(len(x['entered']) for x in membership_changes),'membership_exit_count':sum(len(x['exited']) for x in membership_changes),'membership_changes':membership_changes,'local_unique_raw_files_verified':len(set(local)),'existing_raw_checks':checks,'existing_normalized_checks':normalized,'selected_channel_rows':selected,'current_http_status_counts':dict(Counter(x.get('status','network_failure') for x in json.loads((ROOT/'receipts.json').read_text())))}
(ROOT/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if not isinstance(v,list)},ensure_ascii=False))

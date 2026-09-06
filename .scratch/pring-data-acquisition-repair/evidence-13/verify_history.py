"""Read existing bytes and public parser results only; never ingest or certify."""
import hashlib
import json
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import UTC,datetime
from pathlib import Path
from capture import import_hash
from pring_cycle.official_context import parse_official_context_document
from pring_cycle.official_lpr import parse_lpr_announcement

ROOT=Path(__file__).resolve().parent
CAS=Path('/home/tywin/.local/share/pring-cycle/artifacts/sha256')
now=datetime.now(UTC)
manifest=json.loads((ROOT/'69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec').read_text())
groups=defaultdict(list)
results=[]
for record in manifest['records']:
    raw=(CAS/record['artifact_hash'][:2]/record['artifact_hash']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==record['artifact_hash']
    families=['lpr'] if record['lpr'] else record['families']
    for family in families:
        result={**record,'family':family,'bytes':len(raw)}
        try:
            if family=='lpr':
                parsed=parse_lpr_announcement(raw,source_url=record['source_url'],expected_period=record['period'],fetched_at=now)
            else:
                parsed=parse_official_context_document(raw,family=family,source_url=record['source_url'],expected_period=record['period'],fetched_at=now)
            result.update(status='parsed',parsed=asdict(parsed),release_same_as_manifest=(str(parsed.release_at.isoformat()) if parsed.release_at else None)==record['release_at'])
        except Exception as error:
            result.update(status='parse_failed',error_type=type(error).__name__,error=str(error))
        results.append(result); groups[family].append(result)
selected=[]
for family,records in sorted(groups.items()):
    latest=max(x['period'] for x in records)
    selected.extend(x for x in records if x['period']==latest)
existing={x['sha256'] for x in json.loads((ROOT/'imports.json').read_text())}
for record in selected:
    if record['artifact_hash'] not in existing:
        import_hash(record['artifact_hash']); existing.add(record['artifact_hash'])
summary={family:{'documents':len(rows),'periods':len({r['period'] for r in rows}),'first_period':min(r['period'] for r in rows),'last_period':max(r['period'] for r in rows),'parse_status':dict(Counter(r['status'] for r in rows)),'exact_time_parsed':sum(r.get('parsed',{}).get('release_at') is not None for r in rows),'date_only_parsed':sum(r.get('parsed',{}).get('release_at') is None and r.get('parsed',{}).get('public_available_at') is not None for r in rows),'unknown_time_parsed':sum(r['status']=='parsed' and r['parsed']['public_available_at'] is None for r in rows),'release_changed_by_current_parser':sum(not r.get('release_same_as_manifest',True) for r in rows)} for family,rows in groups.items()}
out={'verified_at':now.isoformat(),'raw_record_count':len(manifest['records']),'raw_bytes':sum(len((CAS/x['artifact_hash'][:2]/x['artifact_hash']).read_bytes()) for x in manifest['records']),'network_requests':0,'database_written':False,'certification_created':False,'parser_source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path('src/pring_cycle/official_context.py'),Path('src/pring_cycle/official_lpr.py'))},'families':summary,'selected_current_samples':[{'family':r['family'],'period':r['period'],'sha256':r['artifact_hash'],'url':r['source_url']} for r in selected],'results':results}
(ROOT/'history-verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))

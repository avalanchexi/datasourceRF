import json
from pathlib import Path
folder=Path(__file__).resolve().parent
document=json.loads((folder/'frozen-bundle.json').read_bytes())
size=lambda value:len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())
out={'bundle_fields':{key:size(value) for key,value in document.items()},
     'structured_context_fields':{key:size(value) for key,value in document['structured_context'].items()},
     'allowed_evidence_id_count':len(document['allowed_evidence_ids']),
     'instruction':'Size measurements only; no input pruning or certification.'}
(folder/'bundle-size-inspection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False))

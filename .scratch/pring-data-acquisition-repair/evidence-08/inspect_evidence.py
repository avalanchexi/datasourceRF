import hashlib
import json
from pathlib import Path
from html.parser import HTMLParser
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip = max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())

for record in json.loads((ROOT / 'receipts.json').read_text()) + json.loads((ROOT / 'imports.json').read_text()):
    if 'sha256' not in record: continue
    path=ROOT/record['local_file']; raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == record['sha256'] and len(raw)==record['bytes']
    if raw.startswith(b'%PDF'):
        pages=PdfReader(path).pages
        out='\n'.join(f'--- page {i+1} ---\n'+p.extract_text() for i,p in enumerate(pages))
    elif raw.lstrip().startswith((b'<!',b'<html',b'<HTML')):
        parser=Text(); parser.feed(raw.decode('utf-8',errors='replace')); out='\n'.join(parser.parts)
    else: continue
    (ROOT/(path.name+'.txt')).write_text(out, encoding='utf-8')

listings=[]
for digest in ('29398877a441e7c24ddc18d4301f20661dc9ae75e5c1c9bca88d07e68f4c4787','4f63ca8ba58609fb71e9a787298eb0761079363869e66ad7f34d9967c63cd643','76bd8b47dc15968eb7e91ff0becb0bbad322488cfa026f53d578c182b5152eaf'):
    data=json.loads((ROOT/digest).read_text())['data']
    listings.extend(dict(zip(data['fields'],v)) for v in data['items'])
print('LISTING SAMPLE',json.dumps([x for x in listings if x['list_date'] in ('20260318','2026-03-18') or x['ts_code'] in ('600636.SH','600355.SH')], ensure_ascii=False))
manifest=json.loads((ROOT/'dfa264f956d2c07def24190b0fda8dc8da6160b6c37000fe165c9cde9b834110').read_text())
print('MANIFEST KEYS',list(manifest))
print('SAMPLE RECORD',json.dumps(manifest.get('raw_receipts',[])[:1]))

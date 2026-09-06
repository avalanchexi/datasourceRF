"""Local evidence inspection and human review aids; no ingestion or certification."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip(): self.parts.append(re.sub(r'\s+',' ',data).strip())

def inspect():
    rows=[]
    for p in sorted(ROOT.iterdir()):
        if not re.fullmatch('[a-f0-9]{64}',p.name): continue
        raw=p.read_bytes(); assert hashlib.sha256(raw).hexdigest()==p.name
        if raw.startswith(b'%PDF'):
            from pypdf import PdfReader
            txt='\n'.join(f'PAGE {i+1}\n'+page.extract_text() for i,page in enumerate(PdfReader(p).pages))
        elif b'<html' in raw[:1000].lower() or b'<!doctype' in raw[:1000].lower():
            encoding='gb18030' if re.search(br'charset\s*=\s*["\']?(?:gb2312|gbk|gb18030)',raw[:3000],re.I) else 'utf-8'
            t=Text(); t.feed(raw.decode(encoding,errors='replace')); txt='\n'.join(t.parts)
        else: continue
        (ROOT/(p.name+'.txt')).write_text(txt,encoding='utf-8')
        rows.append({'sha256':p.name,'text_lines':len(txt.splitlines()),'replacement_characters':txt.count('\ufffd')})
    hist=json.loads((ROOT/'history-verification.json').read_text())
    latest=[]
    for sample in hist['selected_current_samples']:
        r=next(x for x in hist['results'] if x['family']==sample['family'] and x['artifact_hash']==sample['sha256'])
        latest.append({'family':sample['family'],'period':r['period'],'url':r['source_url'],'sha256':r['artifact_hash'],'release_at':r['parsed']['release_at'],'scalars':r['parsed'].get('scalars',r['parsed'])})
    (ROOT/'sample-inspection.json').write_text(json.dumps({'text_extractions':rows,'latest_family_samples':latest},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(latest,ensure_ascii=False,indent=2))

if __name__=='__main__': inspect()

"""Read only captured public bytes; derived text is not a second source."""
import hashlib,json,re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
ROOT=Path(__file__).resolve().parent
class Text(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.skip=0;self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if tag=='a':
            href=dict(attrs).get('href')
            if href:self.links.append(href)
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip():self.parts.append(re.sub(r'\s+',' ',data).strip())
rows=[]
receipts=json.loads((ROOT/'receipts.json').read_text())
for p in sorted(ROOT.iterdir()):
    if not re.fullmatch('[a-f0-9]{64}',p.name):continue
    raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==p.name
    rr=next((r for r in receipts if r.get('sha256')==p.name),{})
    base=rr.get('final_url',rr.get('url',''))
    links=[]
    if raw.startswith(b'%PDF'):
        from pypdf import PdfReader
        txt='\n'.join(f'PAGE {i+1}\n'+(page.extract_text() or '') for i,page in enumerate(PdfReader(p).pages))
    elif b'<html' in raw[:1000].lower() or b'<!doctype' in raw[:1000].lower():
        encoding='gb18030' if re.search(br'charset\s*=\s*["\']?(?:gb2312|gbk|gb18030)',raw[:3000],re.I) else 'utf-8'
        t=Text();t.feed(raw.decode(encoding,errors='replace'));txt='\n'.join(t.parts)
        links=sorted(set(urljoin(base,x) for x in t.links))
    else:continue
    (ROOT/(p.name+'.txt')).write_text(txt,encoding='utf-8')
    rows.append({'sha256':p.name,'url':base,'lines':len(txt.splitlines()),'replacement_characters':txt.count('\ufffd'),'links':links})
(ROOT/'text-inspection.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps([{k:r[k] for k in ('sha256','url','lines','replacement_characters')} for r in rows],ensure_ascii=False))

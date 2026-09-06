"""Read installed and workspace parser identity; CRLF and LF byte hashes kept separately."""
import hashlib,inspect,json
from pathlib import Path
import pring_cycle.official_context as c
import pring_cycle.official_lpr as l

rows=[]
for module in (c,l):
    installed=Path(inspect.getfile(module));source=Path('src/pring_cycle')/installed.name
    a=installed.read_bytes();b=source.read_bytes()
    same=a.replace(b'\r\n',b'\n')==b.replace(b'\r\n',b'\n')
    assert same
    rows.append({'installed_file':str(installed),'workspace_file':str(source),'installed_sha256':hashlib.sha256(a).hexdigest(),'workspace_sha256':hashlib.sha256(b).hexdigest(),'normalized_text_equal':same,'normalized_sha256':hashlib.sha256(a.replace(b'\r\n',b'\n')).hexdigest()})
(Path(__file__).resolve().parent/'parser-identity.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows))

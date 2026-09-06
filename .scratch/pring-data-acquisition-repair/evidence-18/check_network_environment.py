import json,os
from pathlib import Path
keys=('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy','SSL_CERT_FILE','NODE_EXTRA_CA_CERTS')
out={'network_variable_presence':{k:bool(os.environ.get(k)) for k in keys},'values_logged':False}
Path(__file__).with_name('network-environment.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))

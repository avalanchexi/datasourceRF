"""Check only the user's already-enabled Windows loopback proxy with public HEADs."""
import json,time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC,datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler,Request,build_opener

def check(url):
    started=time.monotonic()
    result={'url':url,'method':'HEAD','proxy':'http://127.0.0.1:10809','credentials_sent':False,
            'started_at':datetime.now(UTC).isoformat()}
    try:
        opener=build_opener(ProxyHandler({'http':result['proxy'],'https':result['proxy']}))
        with opener.open(Request(url,method='HEAD'),timeout=8) as response:
            result['http_status']=response.status
    except HTTPError as error:
        result['http_status']=error.code
    except Exception as error:
        result['error_type']=type(error).__name__
        result['reason']=str(error)[:300]
    result['duration_seconds']=round(time.monotonic()-started,3)
    return result
with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(check,('https://chatgpt.com/','https://api.anthropic.com/')))
Path(__file__).with_name('existing-proxy-connectivity.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results))

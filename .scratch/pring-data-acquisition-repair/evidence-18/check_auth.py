"""Ask the installed CLI for auth status; retain categorical status only, never credentials."""
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

out={'checked_at':datetime.now(UTC).isoformat(),'credentials_read_by_application':False}
for name,command in [('codex_cli',['/usr/local/bin/codex','login','status']),
                     ('claude_code_cli',['/home/tywin/.npm-global/bin/claude','auth','status'])]:
    try:
        result=subprocess.run(command,capture_output=True,text=True,timeout=20)
    except subprocess.TimeoutExpired:
        out[name]={'classification':'status_timed_out'}
        continue
    text=(result.stdout+'\n'+result.stderr).lower()
    entry={'exit_code':result.returncode,'status_output_retained':False}
    if name=='codex_cli':
        entry['classification']='logged_in_chatgpt' if 'chatgpt' in text and 'logged in' in text else ('logged_in_api_key' if 'api key' in text and 'logged in' in text else ('not_logged_in' if 'not logged in' in text else 'unclassified'))
    else:
        try:
            doc=json.loads(result.stdout)
        except json.JSONDecodeError:
            entry['classification']='unclassified'
        else:
            entry['status']={key:doc[key] for key in ('loggedIn','authMethod','apiProvider') if key in doc}
    out[name]=entry
folder=Path(__file__).resolve().parent
(folder/'auth-status.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False))

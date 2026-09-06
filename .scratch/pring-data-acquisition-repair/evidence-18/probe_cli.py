"""One real report CLI attempt per adapter against a frozen historical bundle.

This diagnostic never writes the production database or publishes a model/report.
Captured child output stays in its isolated native runtime; only hashes/outcomes
are printed. It is not proof that the historical input catalog is certified.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.reports import CliReportAdapter, EvidenceBundle

folder = Path(__file__).resolve().parent
mode = sys.argv[1] if len(sys.argv) > 1 else 'inspect'
label = sys.argv[2] if len(sys.argv) > 2 else 'initial'
native = Path('/home/tywin/.cache/pring-cycle/verification/repair-18-initial-cli')
native.mkdir(parents=True, exist_ok=True, mode=0o700)
tempfile.tempdir = str(native)
db = Path('/home/tywin/.local/share/pring-cycle/pring-cycle.sqlite3')
if (folder / 'frozen-bundle.json').exists():
    raw = (folder / 'frozen-bundle.json').read_bytes()
    row = (json.loads(raw)['bundle_id'], hashlib.sha256(raw).hexdigest(), raw.decode())
else:
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        row = connection.execute(
            'SELECT bundle_id, bundle_hash, document_json FROM evidence_bundle ORDER BY created_at DESC LIMIT 1'
        ).fetchone()
assert row is not None
raw = row[2].encode()
assert hashlib.sha256(raw).hexdigest() == row[1]
(folder / 'frozen-bundle.json').write_bytes(raw)
document = json.loads(raw)
for key in ('report_cutoff', 'system_as_of'):
    document[key] = datetime.fromisoformat(document[key])
for key in ('allowed_evidence_ids', 'allowed_governance_refs', 'support', 'counterevidence', 'governance_gaps'):
    document[key] = tuple(document[key])
bundle = EvidenceBundle(**document)
summary = {'read_at': datetime.now(UTC).isoformat(), 'bundle_id': row[0], 'bundle_hash': row[1],
           'bundle_bytes': len(raw), 'model_version_id': bundle.model_version_id,
           'target_business_date': bundle.target_business_date, 'production_writes': 0,
           'formal_publication': False, 'native_diagnostic_path': str(native), 'cli': {}}
for adapter, executable in [('codex_cli', '/usr/local/bin/codex'),
                            ('claude_code_cli', '/home/tywin/.npm-global/bin/claude')]:
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=30)
    summary['cli'][adapter] = {'version': version.stdout.strip(), 'version_exit_code': version.returncode}
    help_command = [executable, *(['exec'] if adapter == 'codex_cli' else []), '--help']
    help_result = subprocess.run(help_command, capture_output=True, timeout=30)
    (folder / (adapter + '-help.txt')).write_bytes(help_result.stdout)
if mode == 'inspect':
    (folder / 'environment-inspection.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(0)
assert mode in {'codex_cli', 'claude_code_cli'}
assert not (folder / (mode + '-' + label + '.json')).exists(), 'do not silently repeat the real attempt'
actual_popen = subprocess.Popen
records = []

def trace_popen(*args, **kwargs):
    process = actual_popen(*args, **kwargs)
    communicate = process.communicate
    record = {'started_at': datetime.now(UTC).isoformat()}
    records.append(record)

    def trace_communication(*a, **kw):
        result = communicate(*a, **kw)
        record.update({'completed_at': datetime.now(UTC).isoformat(), 'exit_code': process.returncode})
        for label, content in zip(('stdout', 'stderr'), result):
            data = (content or '').encode()
            path = native / (mode + '.' + globals()['label'] + '.' + label)
            path.write_bytes(data)
            record[label] = {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        return result

    process.communicate = trace_communication
    return process

subprocess.Popen = trace_popen
started = datetime.now(UTC)
try:
    response = CliReportAdapter(mode).generate(bundle)
finally:
    subprocess.Popen = actual_popen
output = {'adapter': mode, 'environment': summary, 'started_at': started.isoformat(),
          'completed_at': datetime.now(UTC).isoformat(), 'response': asdict(response),
          'physical_processes': records, 'new_certifications': 0}
(folder / (mode + '-' + label + '.json')).write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'adapter': mode, 'status': response.status,
                  'classification': response.error_classification,
                  'tool_events': response.tool_events, 'physical_processes': records}, ensure_ascii=False))

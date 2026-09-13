"""Read saved research originals and recompute finite independent expectations."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import re

BASE = Path('/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair')
OUTPUT = BASE / 'verification-futures-research-root-535.json'
assert not OUTPUT.exists()
report = BASE / 'research-11-12-prerequisites-443.md'
assert hashlib.sha256(report.read_bytes()).hexdigest() == '9a14b453417d4f9345cf49380799e36a9d72c5caff972d3a99da910806bf84c0'
originals = {}
data = {}
for directory in ('futures-metadata-204', 'futures-daily-206'):
    receipt_file = BASE / directory / 'receipts.json'
    receipts = json.loads(receipt_file.read_bytes())['receipts']
    for receipt in receipts:
        path = BASE / directory / receipt['local_file']
        raw = path.read_bytes()
        assert len(raw) == receipt['byte_count']
        assert hashlib.sha256(raw).hexdigest() == receipt['sha256']
        doc = json.loads(raw)
        fields, items = doc['data']['fields'], doc['data']['items']
        assert doc['code'] == 0 and len(items) == receipt['returned_rows']
        assert all(len(item) == len(fields) for item in items)
        rows = [dict(zip(fields, item, strict=True)) for item in items]
        key = (receipt['api_name'], json.dumps(receipt['parameters'], sort_keys=True))
        assert key not in data
        data[key] = rows
        originals[path.relative_to(BASE).as_posix()] = receipt['sha256']
assert len(originals) == 152
for ref in re.findall(r'\]\(([^)]+)\)', report.read_text()):
    relative = ref.split('#')[0]
    if re.search(r'/[a-f0-9]{64}\.(?:json|dat|txt|html|pdf)$', relative):
        path = BASE / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == path.stem
        originals[relative] = digest

def rows_for(api, **params):
    return next(rows for (name, encoded), rows in data.items()
                if name == api and all(json.loads(encoded).get(k) == v for k, v in params.items()))

def prices(code, day):
    matches = [row for row in rows_for('fut_daily', ts_code=code) if row['trade_date'] == day]
    assert len(matches) == 1
    row = matches[0]
    return tuple(Fraction(str(row[k])) for k in ('pre_settle', 'settle'))

calendar = rows_for('fut_trade_cal', exchange='INE')
open_days = sorted(row['cal_date'] for row in calendar if row['is_open'] == 1)
boundaries = {day: [v for v in open_days if day < v <= '20260831'] for day in ('20260814', '20260817')}
assert boundaries['20260814'] == ['20260817','20260818','20260819','20260820','20260821','20260824','20260825','20260826','20260827','20260828','20260831']
assert len(boundaries['20260817']) == 10
assert prices('SC2609.INE', '20260814') == (Fraction('554.2'), Fraction('554.9'))
assert prices('SC2610.INE', '20260817') == (Fraction('550.5'), Fraction('559.6'))
expectations = {
    'CU2604.SHF': ('100780','99880'), 'RB2604.SHF': ('3075','3112'),
    'PP2604.DCE': ('7672','8097'), 'CF2605.ZCE': ('15255','15425'),
    'TA2604.ZCE': ('5898','6286'), 'RU2604.SHF': ('16615','17245'),
    'SP2604.SHF': ('5262','5330'), 'SC2604.INE': ('659.7','746.6'),
}
returns = {}
for code, pair in expectations.items():
    previous, settle = prices(code, '20260309')
    assert (previous, settle) == tuple(map(Fraction, pair))
    assert prices(code, '20260306')[1] == previous
    returns[code] = settle / previous - 1
basket = sum(Fraction(2,15) * returns[code] for code in ('CU2604.SHF','RB2604.SHF','PP2604.DCE','RU2604.SHF','SP2604.SHF'))
basket += Fraction(1,15) * (returns['CF2605.ZCE'] + returns['TA2604.ZCE'])
basket += Fraction(1,5) * returns['SC2604.INE']
assert basket == Fraction(87683944158086013297667733,1904003384605774980094318500)
record = {
    'status': 'passed', 'kind': 'saved-original research verification, not application testing or certification',
    'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'report': {'path': report.name, 'sha256': hashlib.sha256(report.read_bytes()).hexdigest()},
    'originals': originals, 'transport_originals': 152,
    'contract_metadata_rows': sum(len(rows) for (api, _), rows in data.items() if api == 'fut_basic'),
    'daily_rows': sum(len(rows) for (api, _), rows in data.items() if api == 'fut_daily'),
    'ine_boundary_days': boundaries, 'first_day_prices': expectations,
    'first_day_return': str(basket), 'first_day_level': str(1000 * (1 + basket)),
    'network_requests': 0, 'production_writes': 0,
    'remaining': ['PP publisher sample', 'historical identities/calendars/events PUBLIC', 'ticket11 input software', 'ticket12 derived software', 'real certification and 120-day acceptance'],
}
OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:record[k] for k in ('status','transport_originals','contract_metadata_rows','daily_rows','first_day_return','network_requests')}))

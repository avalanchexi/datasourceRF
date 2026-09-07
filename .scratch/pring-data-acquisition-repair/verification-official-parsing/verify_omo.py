"""Independently verify saved OMO table literals against the fixed preparation."""
import hashlib
import json
import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.stack = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            table = [self.getpos()[0], []]
            self.tables.append(table)
            self.stack.append(table)
        elif tag == "tr" and self.stack:
            self.stack[-1][1].append([])
        elif tag in {"td", "th"} and self.stack:
            self.cell = [self.getpos()[0], ""]
            self.stack[-1][1][-1].append(self.cell)

    def handle_data(self, value):
        if self.cell is not None:
            self.cell[1] += value

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.cell = None
        elif tag == "table":
            self.stack.pop()


base = Path(__file__).resolve().parents[1]
raw = (base / "p1-omo-full-value-audit.md").read_bytes()
assert len(raw) == 81481 and hashlib.sha256(raw).hexdigest() == "d1af0e4bd294fedede1aaa32be505c88a013965c36be2d4d297f5f8b616c617e"
report = raw.decode("utf-8")
links = [item for item in re.findall(r"\]\(([^)]+)\)", report) if "://" not in item]
assert len(links) == 136
for item in links:
    assert (Path(item) if item.startswith("//") else base / item).is_file(), item
for path, length, sha in re.findall(r"\| (evidence-[^ |]+) \| (\d+) \| ([a-f0-9]{64}) \|", report):
    data = (base / path).read_bytes()
    assert len(data) == int(length) and hashlib.sha256(data).hexdigest() == sha
prep = json.loads((base / "evidence-13-preparation/preparation.json").read_text(encoding="utf-8"))
results = {item["artifact_sha256"]: item for item in prep["data"]["results"] if item["family"] == "pbc_omo_notice"}
assert len(results) == 131
count = rate_count = zero_count = total_bytes = 0
seen = set()
for line in report.splitlines():
    if not re.match(r"\| R\d{3} \| \[", line):
        continue
    cols = [item.strip() for item in line.split("|")[1:-1]]
    name, date_url, raw_link, size, sha, visible, created = cols
    date, url = re.match(r"\[(\d{4}-\d{2}-\d{2}) / .+?\]\(([^)]+)\)", date_url).groups()
    location = re.search(r"\]\(([^)]+)\)", raw_link).group(1)
    data = Path(location).read_bytes()
    assert len(data) == int(size) and hashlib.sha256(data).hexdigest() == sha
    assert sha not in seen
    seen.add(sha)
    total_bytes += len(data)
    html = data.decode("utf-8")
    parser = Tables()
    parser.feed(html)
    start, rows = parser.tables[15]
    assert start == 352 and len(rows) == 2
    header = [''.join(cell[1].split()) for cell in rows[0]]
    values = [''.join(cell[1].split()) for cell in rows[1]]
    assert values[0] == "7天"
    if len(header) == 4:
        assert header == ["期限", "操作利率", "投标量", "中标量"]
        assert rows[1][-1][0] == 364 and rows[1][1][0] == 362
        assert values[1] == "1.40%"
        rate_count += 1
    else:
        assert header == ["期限", "投标量", "中标量"]
        assert rows[1][-1][0] == 362 and values[1:] == ["0亿元", "0亿元"]
        zero_count += 1
    amount = Decimal(values[-1].removesuffix("亿元"))
    assert values[-2] == values[-1]
    prose = ''.join(re.sub(r"<[^>]+>", "", html.splitlines()[349]).split())
    year, month, day = map(int, date.split("-"))
    assert f"{year}年{month}月{day}日" in prose
    assert ("7天期逆回购操作量为零" in prose) if amount == 0 else (f"开展了{amount}亿元7天期逆回购操作" in prose)
    assert visible == date + " 09:20:30" and visible in html and created in html
    scalars = results[sha]["parsed"]["scalars"]
    assert len(scalars) == (2 if len(header) == 4 else 1)
    row = next(line for line in report.splitlines() if line.startswith(f"| {name} / {date} |"))
    assert f"{values[-1]} → {amount}" in row
    for scalar in scalars:
        metric = scalar["metric_id"]
        is_amount = metric == "CN_OMO_7D_AMOUNT"
        assert metric in {"CN_OMO_7D_AMOUNT", "CN_OMO_7D_RATE"}
        assert Decimal(str(scalar["value"])) == (amount if is_amount else Decimal("1.40"))
        assert scalar["unit"] == ("hundred_million_cny" if is_amount else "percent")
        assert scalar["source_field"] == ("injection_100m" if is_amount else "operation_rate_pct")
        assert scalar["dimensions"] == ({"measure": "injection"} if is_amount else {})
        assert scalar["period_start"] == scalar["period_end"] == date
        count += 1
assert (len(seen), total_bytes, count, rate_count, zero_count) == (131, 4013310, 252, 121, 10)
result = dict(originals=131, raw_bytes=total_bytes, exact_scalars=count, rates=rate_count, explicit_zero_amounts=zero_count, local_links=len(links), source_certifications=0, model_adoptions=0)
(Path(__file__).parent / "omo-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))

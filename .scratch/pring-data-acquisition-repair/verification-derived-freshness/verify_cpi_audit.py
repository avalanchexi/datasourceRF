"""Recheck the independent report's literal cells against raw HTML and saved preparation."""

import calendar
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
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self.tables[-1].append([])
        elif tag in {"td", "th"}:
            self.cell = [self.getpos()[0], ""]
            self.tables[-1][-1].append(self.cell)

    def handle_data(self, data):
        if self.cell is not None:
            self.cell[1] += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.cell = None


def documents(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from documents(child)
    elif isinstance(value, list):
        for child in value:
            yield from documents(child)


base = Path(__file__).resolve().parents[1]
report = base / "p1-cpi-full-value-audit.md"
raw = report.read_bytes()
assert len(raw) == 19071
assert hashlib.sha256(raw).hexdigest() == "1f57b4ee4670e928364225944f685823ef30817a7968a42194892489d1c8c751"
text = raw.decode("utf-8")
links = [item for item in re.findall(r"\]\(([^)]+)\)", text) if "://" not in item]
assert len(links) == 13
for item in links:
    assert (base / item).is_file(), item
originals = {}
for line in text.splitlines():
    if not re.match(r"\| R\d{2} \| \[", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    target = re.search(r"\]\(([^)]+)\)", fields[2]).group(1)
    content = (base / target).read_bytes()
    sha = fields[4].strip("`")
    assert len(content) == int(fields[3])
    assert hashlib.sha256(content).hexdigest() == sha
    parser = Tables()
    parser.feed(content.decode("utf-8"))
    assert len(parser.tables) == 2
    assert [len(table) for table in parser.tables] == [48, 48]
    normalized = [[[''.join(cell[1].split()) for cell in row] for row in table] for table in parser.tables]
    assert normalized[0] == normalized[1]
    originals[fields[0]] = (sha, len(content), parser.tables[0])
assert len(originals) == 8
assert sum(item[1] for item in originals.values()) == 1850811
preparation = json.loads((base / "evidence-13-preparation/preparation.json").read_text(encoding="utf-8"))
candidates = {
    doc["artifact_sha256"]: doc["parsed"]["scalars"]
    for doc in documents(preparation)
    if doc.get("family") == "nbs_core_cpi" and "parsed" in doc
}
assert len(candidates) == 8
assert sum(len(rows) for rows in candidates.values()) == 46
verified = []
for line in text.splitlines():
    if not re.match(r"\| \d{2} \| R\d{2} /", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    reference, period = fields[1].split(" / ")
    sha, _, table = originals[reference]
    table_id, row, column, source_line = map(int, re.fullmatch(r"T(\d+) R(\d+) C(\d+) L(\d+)", fields[4]).groups())
    assert table_id == 1
    cell = table[row - 1][column - 1]
    assert cell[0] == source_line
    expected = Decimal(fields[5])
    assert Decimal(''.join(cell[1].split())) == expected == Decimal(fields[6])
    core = fields[2] == "核心"
    assert row == (9 if core else 2)
    label = ''.join(table[row - 1][0][1].split())
    assert ("不包括食品和能源" in label) if core else label == "居民消费价格"
    measure = "cumulative_average_yoy" if fields[3] == "累计" else fields[3]
    assert column == {"mom": 2, "yoy": 3, "cumulative_average_yoy": 4}[measure]
    metric = "CN_CORE_CPI" if core else "CN_CPI_HEADLINE"
    selected = [item for item in candidates[sha] if item["metric_id"] == metric and item["dimensions"]["measure"] == measure]
    assert len(selected) == 1
    candidate = selected[0]
    assert Decimal(str(candidate["value"])) == expected
    assert candidate["dimensions"]["category"] == ("ex_food_energy" if core else "headline")
    assert candidate["unit"] == "percent" and candidate["period_kind"] == "month"
    year, month = map(int, period.split("-"))
    assert candidate["period_start"] == f"{period}-01"
    assert candidate["period_end"] == f"{period}-{calendar.monthrange(year, month)[1]}"
    verified.append(fields[0])
assert len(set(verified)) == 46
print(json.dumps({"verified_cells": 46, "conflicts": 0, "originals": 8, "original_bytes": 1850811,
                  "local_links": len(links), "report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest(),
                  "scope": "raw HTML cell line, identity, period, unit and literal vs report and saved preparation",
                  "network_requests": 0, "application_parser_calls": 0}, indent=2))

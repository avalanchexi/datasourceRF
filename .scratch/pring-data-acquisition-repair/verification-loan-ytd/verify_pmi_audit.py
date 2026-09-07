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
report = base / "p1-pmi-full-value-audit.md"
raw = report.read_bytes()
assert len(raw) == 21325
assert hashlib.sha256(raw).hexdigest() == "02901b12706b0101be06a4c5b74873cd46322fbefb9b6507dbbe7c8bfe3de7ef"
text = raw.decode("utf-8")
links = [item for item in re.findall(r"\]\(([^)]+)\)", text) if "://" not in item]
assert len(links) == 12
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
    assert len(parser.tables) == 8
    assert [len(table) for table in parser.tables[:2]] == [16, 15]
    normalized = [[[''.join(cell[1].split()) for cell in row] for row in table] for table in parser.tables]
    assert normalized[0] == normalized[4]
    assert normalized[1] == normalized[5]
    originals[fields[0]] = (sha, len(content), parser.tables)
assert len(originals) == 7
assert sum(item[1] for item in originals.values()) == 2894481
preparation = json.loads((base / "evidence-13-preparation/preparation.json").read_text(encoding="utf-8"))
candidates = {
    doc["artifact_sha256"]: doc["parsed"]["scalars"]
    for doc in documents(preparation)
    if doc.get("family") == "nbs_pmi" and "parsed" in doc
}
assert len(candidates) == 7
assert sum(len(rows) for rows in candidates.values()) == 56
verified = []
for line in text.splitlines():
    if not re.match(r"\| \d{2} \| R\d{2} /", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    reference, period = fields[1].split(" / ")
    sha, _, tables = originals[reference]
    table_id, row, column, source_line = map(int, re.fullmatch(r"T(\d+) R(\d+) C(\d+) L(\d+)", fields[4]).groups())
    table = tables[table_id - 1]
    cell = table[row - 1][column - 1]
    assert cell[0] == source_line
    expected = Decimal(fields[5])
    assert Decimal(''.join(cell[1].split())) == expected == Decimal(fields[6])
    metric = {"活动": "CN_PMI_ACTIVITY", "库存": "CN_PMI_INVENTORY", "价格": "CN_PMI_PRICES"}[fields[2]]
    series = fields[3]
    assert (table_id, row, column) == {
        "manufacturing": (1, 16, 2), "production": (1, 16, 3),
        "new_orders": (1, 16, 4), "purchase_volume": (2, 15, 4),
        "raw_materials": (1, 16, 5), "finished_goods": (2, 15, 7),
        "purchase_prices": (2, 15, 5), "output_prices": (2, 15, 6),
    }[series]
    selected = [item for item in candidates[sha] if item["metric_id"] == metric and item["dimensions"] == {"series": series, "measure": "level"}]
    assert len(selected) == 1
    candidate = selected[0]
    assert Decimal(str(candidate["value"])) == expected
    assert candidate["source_field"] == ("manufacturing_pmi" if series == "manufacturing" else series)
    assert candidate["unit"] == "diffusion_index_points" and candidate["period_kind"] == "month"
    year, month = map(int, period.split("-"))
    dates = [''.join(item[0][1].split()) for item in table[:row] if item]
    assert int(re.search(r"(\d+)月", dates[-1]).group(1)) == month
    assert int(re.findall(r"(\d{4})年", ' '.join(dates))[-1]) == year
    assert candidate["period_start"] == f"{period}-01"
    assert candidate["period_end"] == f"{period}-{calendar.monthrange(year, month)[1]}"
    verified.append(fields[0])
assert len(set(verified)) == 56
print(json.dumps({"verified_cells": 56, "conflicts": 0, "originals": 7, "original_bytes": 2894481,
                  "local_links": len(links), "report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest(),
                  "scope": "raw HTML cell line, identity, period, unit and literal vs report and saved preparation",
                  "network_requests": 0, "application_parser_calls": 0}, indent=2))

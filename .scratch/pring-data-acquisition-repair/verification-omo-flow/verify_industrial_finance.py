"""Independently compare report literals with original cells and saved candidate values."""

import calendar
import hashlib
import json
import re
from decimal import Decimal
from html import unescape
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
raw = (base / "p1-industrial-finance-full-value-audit.md").read_bytes()
assert len(raw) == 24950
assert hashlib.sha256(raw).hexdigest() == "f14f4f98f8050386a7f9f9f0f3e4d84c75b56c6dffa743d8b47c6e2ed1d3ab7d"
text = raw.decode("utf-8")
input_fingerprints = 0
for line in text.splitlines():
    match = re.fullmatch(r"\| `([^`]+)` \| (\d+) \| `([a-f0-9]{64})` \|", line)
    if match:
        name, length, digest = match.groups()
        data = (base / name).read_bytes()
        assert len(data) == int(length) and hashlib.sha256(data).hexdigest() == digest
        input_fingerprints += 1
assert input_fingerprints == 5
links = [item for item in re.findall(r"\]\(([^)]+)\)", text) if "://" not in item]
assert len(links) == 12
for item in links:
    assert (base / item).is_file(), item
originals = {}
for line in text.splitlines():
    if not re.match(r"\| R\d{2} \| \[", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    path = re.search(r"\]\(([^)]+)\)", fields[2]).group(1)
    content = (base / path).read_bytes()
    sha = fields[4].strip("`")
    assert len(content) == int(fields[3])
    assert hashlib.sha256(content).hexdigest() == sha
    source = content.decode("utf-8")
    parser = Tables()
    parser.feed(source)
    assert len(parser.tables) == 6
    normalized = [[[''.join(cell[1].split()) for cell in row] for row in table] for table in parser.tables]
    assert normalized[0] == normalized[3] and normalized[1] == normalized[4]
    assert len(parser.tables[0]) == len(parser.tables[1]) == 11
    originals[fields[0]] = (sha, len(content), parser.tables, source.splitlines())
assert len(originals) == 7
assert sum(item[1] for item in originals.values()) == 3401593
contracts = {}
for line in text.splitlines():
    if not re.match(r"\| [FIT]-[a-z-]+ \| CN_", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    dimensions = dict(item.strip().split("=") for item in fields[2].split(";"))
    contracts[fields[0]] = (fields[1], dimensions, fields[3], fields[4], fields[5])
assert len(contracts) == 10
snippets = {}
for line in text.splitlines():
    if not re.match(r"\| R\d{2} \| .* \| S1：", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    source_text = ''.join(unescape(re.sub(r"<[^>]*>", "", originals[fields[0]][3][331])).split())
    pair = tuple(item.split("：", 1)[1] for item in fields[2:4])
    assert all(item in source_text for item in pair)
    snippets[fields[0]] = pair
assert len(snippets) == 7
preparation = json.loads((base / "evidence-13-preparation/preparation.json").read_text(encoding="utf-8"))
candidates = {
    doc["artifact_sha256"]: doc["parsed"]["scalars"]
    for doc in documents(preparation)
    if doc.get("family") == "nbs_industrial_finance" and "parsed" in doc
}
assert len(candidates) == 7 and sum(map(len, candidates.values())) == 70
verified = []
conversions = 0
for line in text.splitlines():
    if not re.match(r"\| \d{2} \| R\d{2} /", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    reference, period = fields[1].split(" / ")
    sha, _, tables, _ = originals[reference]
    key = fields[2]
    literal, source_unit = fields[4].split()
    expected = Decimal(fields[5])
    if fields[3].startswith("T"):
        table_id, row, column, source_line = map(int, re.fullmatch(r"T(\d+) R(\d+) C(\d+) L(\d+)", fields[3]).groups())
        cell = tables[table_id - 1][row - 1][column - 1]
        assert cell[0] == source_line
        assert Decimal(''.join(cell[1].split())) == Decimal(literal)
        if key.startswith("F-"):
            assert table_id == 1 and row == 3
            assert ''.join(tables[0][2][0][1].split()) == "总计"
            item, measure = key.split("-")[1:]
            assert column == {"revenue": 2, "cost": 4, "profit": 6}[item] + (measure == "yoy")
            header = ''.join(tables[0][0][{"revenue": 1, "cost": 2, "profit": 3}[item]][1].split())
            assert header == {"revenue": "营业收入", "cost": "营业成本", "profit": "利润总额"}[item]
        else:
            assert key == "T-days" and (table_id, row, column) == (2, 4, 8)
            assert "产成品存货周转天数" == ''.join(tables[1][0][7][1].split())
    else:
        inventory, turnover = snippets[reference]
        fragment = {
            "I-level": "产成品存货" + literal + "万亿元",
            "I-yoy": "增长" + literal + "%",
            "T-yoy-change": "增加" + literal + "天",
        }[key]
        assert fragment in (turnover if key == "T-yoy-change" else inventory)
    factor = Decimal(10000) if key == "I-level" else Decimal(1)
    conversions += key == "I-level"
    assert Decimal(literal) * factor == expected == Decimal(fields[6])
    metric, dimensions, source_field, unit, kind = contracts[key]
    assert source_unit == {"hundred_million_cny": "万亿元" if key == "I-level" else "亿元", "percent": "%", "days": "天"}[unit]
    selected = [item for item in candidates[sha] if item["metric_id"] == metric and item["dimensions"] == dimensions]
    assert len(selected) == 1
    candidate = selected[0]
    assert Decimal(str(candidate["value"])) == expected
    assert (candidate["source_field"], candidate["unit"], candidate["period_kind"]) == (source_field, unit, kind)
    year, month = map(int, period.split("-"))
    assert candidate["period_start"] == (f"{year}-01-01" if kind == "year_to_month" else f"{period}-01")
    assert candidate["period_end"] == f"{period}-{calendar.monthrange(year, month)[1]}"
    verified.append((sha, metric, tuple(sorted(dimensions.items())), candidate["period_end"]))
assert len(set(verified)) == 70 and conversions == 7
print(json.dumps({"verified_cells": 70, "conflicts": 0, "originals": 7, "original_bytes": 3401593,
                  "local_links": len(links), "paragraph_fragments": 14, "unit_conversions": conversions,
                  "input_fingerprints": input_fingerprints,
                  "report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest(),
                  "scope": "raw cell lines and paragraph literals, identity, units, periods, saved preparation",
                  "network_requests": 0, "application_parser_calls": 0}, indent=2))

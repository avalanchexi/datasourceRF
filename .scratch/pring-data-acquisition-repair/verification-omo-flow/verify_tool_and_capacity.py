"""Independent raw-table verification for two fixed research reports; stdlib only."""

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
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            rows = []
            self.tables.append(rows)
            self.stack.append([rows, None])
        elif self.stack and tag == "tr":
            self.stack[-1][0].append([])
        elif self.stack and tag in {"td", "th"}:
            cell = [self.getpos()[0], ""]
            self.stack[-1][0][-1].append(cell)
            self.stack[-1][1] = cell

    def handle_data(self, data):
        if self.stack and self.stack[-1][1] is not None:
            self.stack[-1][1][1] += data

    def handle_endtag(self, tag):
        if self.stack and tag == "table":
            self.stack.pop()
        elif self.stack and tag in {"td", "th"}:
            self.stack[-1][1] = None


def documents(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from documents(child)
    elif isinstance(value, list):
        for child in value:
            yield from documents(child)


base = Path(__file__).resolve().parents[1]
repo = base.parents[1]
prep_path = base / "evidence-13-preparation/preparation.json"
assert hashlib.sha256(prep_path.read_bytes()).hexdigest() == "a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a"
prep = json.loads(prep_path.read_text(encoding="utf-8"))


def report(name, length, digest, link_count):
    raw = (base / name).read_bytes()
    assert len(raw) == length and hashlib.sha256(raw).hexdigest() == digest
    text = raw.decode("utf-8")
    links = [item for item in re.findall(r"\]\(([^)]+)\)", text) if "://" not in item]
    assert len(links) == link_count
    for item in links:
        assert (base / item).is_file(), item
    return text


def source(path, length, digest):
    raw = path.read_bytes()
    assert len(raw) == length and hashlib.sha256(raw).hexdigest() == digest
    text = raw.decode("utf-8")
    parser = Tables()
    parser.feed(text)
    return text, parser.tables


tool_text = report("p1-tool-liquidity-full-value-audit.md", 25421,
                   "13a84f6fcd6ee23827c9d4700d3b4af999a5a2ec40455729bdbf432c44b08fbb", 12)
tool_candidates = {doc["artifact_sha256"]: doc["parsed"]["scalars"] for doc in documents(prep)
                   if doc.get("family") == "pbc_tool_liquidity_monthly" and "parsed" in doc}
assert len(tool_candidates) == 8 and sum(map(len, tool_candidates.values())) == 192
verified = []
zeros = negatives = raw_bytes = missing_markers = months = 0
for section in re.split(r"(?=^## S\d{2}：)", tool_text, flags=re.M)[1:]:
    period = re.match(r"## S\d{2}：(\d{4}-\d{2})", section).group(1)
    path = re.search(r"\[已存原件 S\d{2}\]\(([^)]+)\)", section).group(1)
    length, sha = re.search(r"原件 \*\*(\d+) bytes\*\*，SHA-256 `([a-f0-9]{64})`", section).groups()
    raw_text, tables = source(base / path, int(length), sha)
    raw_bytes += int(length)
    months += 1
    title = re.search(r"原页标题：\*\*([^*]+)\*\*", section).group(1)
    visible = ''.join(unescape(re.sub(r"<[^>]*>", "", raw_text)).split())
    assert title in visible and "单位：亿元" in visible
    for line in section.splitlines():
        if not re.match(r"\| .* \| `-?\d+` /", line):
            continue
        fields = [item.strip() for item in line.split("|")[1:-1]]
        table, row, columns, lines = re.fullmatch(r"T(\d+)/R(\d+)/C([\d,]+); L([\d,]+)", fields[4]).groups()
        cells = tables[int(table)-1][int(row)-1]
        tool = fields[0]
        assert tool in [''.join(cell[1].split()) for cell in cells]
        values = []
        for index, (measure, column, source_line) in enumerate(zip(
            ("injection", "withdrawal", "net_injection"), map(int, columns.split(",")), map(int, lines.split(",")), strict=True
        )):
            literal, prepared = re.fullmatch(r"`(-?\d+)` / `(-?[\d.]+)`", fields[index+1]).groups()
            value = Decimal(literal)
            cell = cells[column-1]
            assert cell[0] == source_line and Decimal(''.join(cell[1].split())) == value == Decimal(prepared)
            selected = [item for item in tool_candidates[sha] if item["metric_id"] == "CN_TOOL_LIQUIDITY_MONTHLY"
                        and item["dimensions"] == {"tool": tool, "measure": measure}]
            assert len(selected) == 1
            candidate = selected[0]
            year, month = map(int, period.split("-"))
            assert candidate["period_start"] == f"{period}-01" and candidate["period_end"] == f"{period}-{calendar.monthrange(year, month)[1]}"
            assert candidate["unit"] == "hundred_million_cny" and candidate["period_kind"] == "month"
            assert candidate["source_field"] == measure + "_100m" and Decimal(str(candidate["value"])) == value
            zeros += value == 0
            negatives += value < 0
            verified.append((sha, tool, measure))
            values.append(value)
        assert values[0] - values[1] == values[2]
    rrr = tables[15][1]
    rrr_text = [''.join(cell[1].split()) for cell in rrr]
    assert "调整法定存款准备金率" in rrr_text
    assert rrr_text[-3:] == ["-", "-", "-"]
    missing_markers += 3
assert len(set(verified)) == 192 and (months, raw_bytes, zeros, negatives, missing_markers) == (8, 357909, 28, 19, 24)

capacity_text = report("p1-capacity-utilization-full-value-audit.md", 13203,
                       "5cce581124ccb722782eb94e6aef5a48bd36faa78d4396ec41568f49feeeb9ed", 8)
capacity_candidates = {doc["artifact_sha256"]: doc["parsed"]["scalars"] for doc in documents(prep)
                       if doc.get("family") == "nbs_capacity_utilization" and "parsed" in doc}
assert len(capacity_candidates) == 3 and sum(map(len, capacity_candidates.values())) == 9
capacity_rows = [
    ("5e067d6d9dbeca559c2ec3ad37abc0a6be6159beb62ccbfe1184fc4b6a7b4da6", 163109, "2025-10-01", "2025-12-31", ["74.9", "-1.3", "74.4"], [353, 355, 357]),
    ("0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a", 128195, "2026-01-01", "2026-03-31", ["73.6", "-0.5"], [348, 350]),
    ("8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8", 168665, "2026-04-01", "2026-06-30", ["73.0", "-1.0", "73.3"], [357, 359, 361]),
]
literal_count = 0
for sha, length, start, end, values, source_lines in capacity_rows:
    path = base / "evidence-13" / sha
    if not path.is_file():
        path = Path("//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256") / sha[:2] / sha
    raw_text, tables = source(path, length, sha)
    assert len(tables) == 2
    normalized = [[[''.join(cell[1].split()) for cell in row] for row in table] for table in tables]
    assert normalized[0] == normalized[1]
    row = tables[0][2]
    assert ''.join(row[0][1].split()) == "工业"
    assert len(row) == (3 if start == "2026-01-01" else 5)
    for index, (literal, source_line) in enumerate(zip(values, source_lines, strict=True)):
        assert row[index+1][0] == source_line and Decimal(''.join(row[index+1][1].split())) == Decimal(literal)
        literal_count += 1
    expected = values if len(values) == 3 else [*values, values[0]]
    for measure, literal, source_field, unit, kind, period_start in zip(
        ("quarter_rate", "yoy_change", "ytd_rate"), expected,
        ("industrial_capacity_utilization_pct", "industrial_capacity_utilization_yoy_change_pp", "industrial_capacity_utilization_ytd_pct"),
        ("percent", "percentage_points", "percent"), ("quarter", "quarter", "year_to_quarter"),
        (start, start, end[:4] + "-01-01"), strict=True
    ):
        selected = [item for item in capacity_candidates[sha] if item["metric_id"] == "CN_CAPACITY_UTILIZATION"
                    and item["dimensions"] == {"industry": "all_industry", "measure": measure}]
        assert len(selected) == 1
        candidate = selected[0]
        assert Decimal(str(candidate["value"])) == Decimal(literal)
        assert (candidate["source_field"], candidate["unit"], candidate["period_kind"], candidate["period_start"], candidate["period_end"]) == (source_field, unit, kind, period_start, end)
assert literal_count == 8
print(json.dumps({"tool_liquidity": {"literal_cells": 192, "originals": 8, "original_bytes": raw_bytes, "negative_values": negatives, "zero_values": zeros, "non_numeric_markers": missing_markers, "local_links": 12},
                  "capacity": {"literal_cells": 8, "existing_alias_mapping_pending": 1, "numeric_identity_checks": 9, "originals": 3, "original_bytes": 459969, "local_links": 8},
                  "network_requests": 0, "application_parser_calls": 0, "source_certification_grants": 0}, indent=2))

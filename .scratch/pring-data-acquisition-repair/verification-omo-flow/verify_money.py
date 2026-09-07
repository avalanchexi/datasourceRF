"""Verify the fixed money audit, preserving its single strict numeric discrepancy."""

import calendar
import hashlib
import json
import re
from decimal import Decimal
from html import unescape
from pathlib import Path


def documents(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from documents(child)
    elif isinstance(value, list):
        for child in value:
            yield from documents(child)


base = Path(__file__).resolve().parents[1]
raw = (base / "p1-money-full-value-audit.md").read_bytes()
assert len(raw) == 16643 and hashlib.sha256(raw).hexdigest() == "44ea8fbc4d0c649343068b987921ea47463f5b8e5067fd39aec09f314cec5eda"
text = raw.decode("utf-8")
links = [item for item in re.findall(r"\]\(([^)]+)\)", text) if "://" not in item]
assert len(links) == 12
for item in links:
    assert (base / item).is_file()
originals = {}
fingerprints = 0
for line in text.splitlines():
    match = re.fullmatch(r"\| `([^`]+)` \| (\d+) \| `([a-f0-9]{64})` \|", line)
    if match:
        name, length, sha = match.groups()
        data = (base / name).read_bytes()
        assert len(data) == int(length) and hashlib.sha256(data).hexdigest() == sha
        fingerprints += 1
    if not re.match(r"\| R\d{2} \| \[", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    path = re.search(r"\]\(([^)]+)\)", fields[2]).group(1)
    content = (base / path).read_bytes()
    sha = fields[4].strip("`")
    assert len(content) == int(fields[3]) and hashlib.sha256(content).hexdigest() == sha
    source_lines = content.decode("utf-8").splitlines()
    paragraph = ''.join(unescape(re.sub(r"<[^>]*>", "", source_lines[358])).split())
    paragraph = paragraph.replace("（", "(").replace("）", ")")
    originals[fields[0]] = (sha, len(content), paragraph)
assert fingerprints == 5 and len(originals) == 7
assert sum(item[1] for item in originals.values()) == 312999
prep = json.loads((base / "evidence-13-preparation/preparation.json").read_text(encoding="utf-8"))
candidates = {doc["artifact_sha256"]: doc["parsed"]["scalars"] for doc in documents(prep)
              if doc.get("family") == "pbc_money" and "parsed" in doc}
assert len(candidates) == 7 and sum(map(len, candidates.values())) == 28
verified = []
differences = []
literal_groups = {}
for line in text.splitlines():
    if not re.match(r"\| \d{2} \| R\d{2} /", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    reference, period = fields[1].split(" / ")
    sha, _, paragraph = originals[reference]
    field = fields[2]
    aggregate = field[:2]
    measure = "yoy" if field.endswith("_yoy") else "balance"
    literal, unit = fields[4].split()
    literal_groups.setdefault((reference, aggregate), {})[measure] = literal
    expected = Decimal(literal) * (10000 if measure == "balance" else 1)
    assert expected == Decimal(fields[5])
    assert unit == ("万亿元" if measure == "balance" else "%")
    selected = [item for item in candidates[sha] if item["metric_id"] == "CN_M1_M2"
                and item["dimensions"] == {"aggregate": aggregate, "measure": measure}]
    assert len(selected) == 1
    candidate = selected[0]
    prepared = Decimal(str(candidate["value"]))
    assert prepared == Decimal(fields[6])
    assert candidate["source_field"] == field and candidate["period_kind"] == "month"
    assert candidate["unit"] == ("hundred_million_cny" if measure == "balance" else "percent")
    year, month = map(int, period.split("-"))
    assert candidate["period_start"] == f"{period}-01" and candidate["period_end"] == f"{period}-{calendar.monthrange(year, month)[1]}"
    if prepared == expected:
        assert fields[7] == "相符"
        verified.append((sha, field))
    else:
        assert fields[7] == "表示微差"
        differences.append({"period": period, "field": field, "expected": str(expected), "prepared": str(prepared), "difference": str(prepared-expected)})
for (reference, aggregate), literals in literal_groups.items():
    paragraph = originals[reference][2]
    assert re.search(re.escape(f"({aggregate.upper()})余额{literals['balance']}万亿元") + r"[，,]同比增长" + re.escape(literals["yoy"]) + "%", paragraph)
assert len(set(verified)) == 27 and len(literal_groups) == 14
assert differences == [{"period": "2026-02", "field": "m2", "expected": "3492200.00", "prepared": "3492200.0000000005", "difference": "5E-10"}]
print(json.dumps({"strict_matches": 27, "numeric_discrepancies": differences, "unlocatable": 0,
                  "identities_units_periods_checked": 28, "originals": 7, "original_bytes": 312999,
                  "input_fingerprints": fingerprints, "local_links": len(links),
                  "report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest(),
                  "network_requests": 0, "application_parser_calls": 0, "tolerance_applied": False}, indent=2))

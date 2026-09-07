"""Independent fixed-source verification; no application imports or writes to old evidence."""

import calendar
import hashlib
import json
import re
import subprocess
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path


class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paragraphs = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.current = [self.getpos()[0], ""]
            self.paragraphs.append(self.current)

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data

    def handle_endtag(self, tag):
        if tag == "p":
            self.current = None


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


def report(name, length, sha, link_count):
    raw = (base / name).read_bytes()
    assert len(raw) == length and hashlib.sha256(raw).hexdigest() == sha
    text = raw.decode("utf-8")
    links = [item for item in re.findall(r"\]\(([^)]+)\)", text) if "://" not in item]
    assert len(links) == link_count
    for item in links:
        assert (base / item.split("#", 1)[0]).is_file(), item
    return text


boundary = report("money-normalization-boundary.md", 18917,
                  "ff7a162bbc71f3e3e765bf7ccbf629208995d3f2963361ca1a6f0dc09b8893d9", 15)
historical = json.loads((Path(__file__).parent / "pre-money-fingerprint.json").read_text(encoding="utf-8"))
input_count = 0
for line in boundary.splitlines():
    match = re.fullmatch(r"\| ([^|]+) \| (\d+) \| ([a-f0-9]{64}) \|", line)
    if not match:
        continue
    name, length, sha = match.groups()
    if name == historical["path"]:
        assert int(length) == historical["bytes"] and sha == historical["sha256"]
    else:
        path = repo / name if not name.startswith("上述UNC") else repo / "tests/fixtures/pbc_money_202602.html"
        raw = path.read_bytes()
        assert len(raw) == int(length) and hashlib.sha256(raw).hexdigest() == sha, name
    input_count += 1
assert input_count == 17
old_source = subprocess.check_output(["git", "show", "ca2780710f2079d59cfb172bde314cba3f547be6:src/pring_cycle/official_context.py"], cwd=repo).decode()
function = old_source.split("def _parse_money(", 1)[1].split("\ndef _year_to_date_label", 1)[0]
function = ("def _parse_money(" + function).rstrip("\n").encode()
assert len(function) == 1566 and hashlib.sha256(function).hexdigest() == "13268fa9b3747daf4932e220b1b43feda2dd881e6e686f8584276d99075a49f8"

loan = report("p1-loan-structure-full-value-audit.md", 66620,
              "2d4d1b4a3e1966cbfeccb0f6892ed31937f941edc7a75d09609424a2e767dcae", 35)
prep_path = base / "evidence-13-preparation/preparation.json"
assert hashlib.sha256(prep_path.read_bytes()).hexdigest() == "a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a"
prep = json.loads(prep_path.read_text(encoding="utf-8"))
candidates = {doc["artifact_sha256"]: doc["parsed"]["scalars"] for doc in documents(prep)
              if doc.get("family") == "pbc_loan_structure" and "parsed" in doc}
assert len(candidates) == 31 and sum(map(len, candidates.values())) == 279
mapping = {
    "H0": ("household", "total", "住户贷款"),
    "HS": ("household", "short_term", "短期贷款"),
    "HL": ("household", "long_term", "中长期贷款"),
    "E0": ("enterprise", "total", "企（事）业单位贷款"),
    "ES": ("enterprise", "short_term", "短期贷款"),
    "EL": ("enterprise", "long_term", "中长期贷款"),
    "EB": ("enterprise", "bill_financing", "票据融资"),
    "N0": ("nonbank_financial", "total", "非银行业金融机构贷款"),
    "A0": ("all_rmb_loans", "total", "人民币贷款"),
}
verified = []
originals = {}
negative = zero = converted = 0
for section in re.split(r"(?=^## L\d{2}：)", loan, flags=re.M)[1:]:
    period = re.match(r"## L\d{2}：(\d{4}-\d{2})", section).group(1)
    target = re.search(r"\[已存原件 L\d{2}\]\(([^)]+)\)", section).group(1)
    length, sha = re.search(r"原件 \*\*(\d+) bytes\*\*，SHA-256 `([a-f0-9]{64})`", section).groups()
    raw = (base / target).read_bytes()
    assert len(raw) == int(length) and hashlib.sha256(raw).hexdigest() == sha
    parser = Paragraphs()
    source = raw.decode("utf-8")
    parser.feed(source)
    paragraph_id, source_line = map(int, re.search(r"贷款原段：P(\d+)/源码L(\d+)", section).groups())
    paragraph = parser.paragraphs[paragraph_id-1]
    assert paragraph[0] == source_line
    paragraph = ''.join(paragraph[1].split())
    assert "分部门看，住户贷款" in paragraph
    title = re.search(r"原页标题：\*\*([^*]+)\*\*", section).group(1)
    assert title in source
    positions = {}
    for line in section.splitlines():
        if not re.match(r"\| (?:H0|HS|HL|E0|ES|EL|EB|N0|A0) \| `", line):
            continue
        fields = [item.strip() for item in line.split("|")[1:-1]]
        key = fields[0]
        literal = fields[1].strip("`")
        start, end = map(int, re.fullmatch(r"C(\d+)–(\d+)", fields[4]).groups())
        assert paragraph[start-1:end] == literal
        borrower, tenor, label = mapping[key]
        assert paragraph[:start-1].endswith(label)
        direction, number, unit = re.fullmatch(r"(增加|减少)([\d.]+)(万亿元|亿元)", literal).groups()
        expected = Decimal(number) * (10000 if unit == "万亿元" else 1) * (-1 if direction == "减少" else 1)
        assert expected == Decimal(fields[2]) == Decimal(fields[3])
        selected = [item for item in candidates[sha] if item["metric_id"] == "CN_LOAN_STRUCTURE"
                    and item["dimensions"] == {"borrower": borrower, "tenor": tenor, "measure": "ytd_increment"}]
        assert len(selected) == 1
        candidate = selected[0]
        assert candidate["source_field"] == "ytd_increment_100m" and candidate["unit"] == "hundred_million_cny"
        assert candidate["period_kind"] == "year_to_month" and candidate["period_start"] == period[:4] + "-01-01"
        year, month = map(int, period.split("-"))
        assert candidate["period_end"] == f"{period}-{calendar.monthrange(year, month)[1]:02d}"
        assert Decimal(str(candidate["value"])) == expected
        negative += expected < 0
        zero += expected == 0
        converted += unit == "万亿元"
        positions[key] = start
        verified.append((sha, borrower, tenor))
    ordered = [positions[key] for key in ("A0", "H0", "HS", "HL", "E0", "ES", "EL", "EB", "N0")]
    assert ordered == sorted(ordered) and len(set(ordered)) == 9
    originals[sha] = len(raw)
assert len(set(verified)) == 279 and len(originals) == 31 and sum(originals.values()) == 1281208
assert (negative, zero, converted) == (49, 0, 157)
print(json.dumps({"money_boundary": {"local_links": 15, "input_fingerprints": 17, "historical_workspace_fingerprint": historical["sha256"], "original_function_verified_from_base": True},
                  "loan_structure": {"verified_literals": 279, "originals": 31, "original_bytes": 1281208, "local_links": 35, "negative_values": negative, "zero_values": zero, "trillion_conversions": converted},
                  "network_requests": 0, "application_parser_calls": 0}, indent=2))

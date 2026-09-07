"""Independent literal and identity verification of the fixed 837-cell SF audit."""

import calendar
import hashlib
import json
import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path


class Blocks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "h1", "h2", "h3"}:
            self.current = [self.getpos()[0], ""]
            self.blocks.append(self.current)

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data

    def handle_endtag(self, tag):
        if tag in {"p", "h1", "h2", "h3"}:
            self.current = None


base = Path(__file__).resolve().parents[1]
repo = base.parents[1]
raw = (base / "p1-social-financing-full-value-audit.md").read_bytes()
assert len(raw) == 147300 and hashlib.sha256(raw).hexdigest() == "a649d2b86df819fa2682c46997a0cec0fd4021c8d702225ddc6ff3a920cb7437"
text = raw.decode("utf-8")
links = [item for item in re.findall(r"\]\(([^)]+)\)", text) if "://" not in item]
assert len(links) == 2
for item in links:
    assert (base / item).is_file()
prep_path = base / "evidence-13-preparation/preparation.json"
assert hashlib.sha256(prep_path.read_bytes()).hexdigest() == "a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a"
prep = json.loads(prep_path.read_text(encoding="utf-8"))
mapping = [
    (None, "社会融资规模"),
    ("renminbi_loans", "对实体经济发放的人民币贷款"),
    ("foreign_currency_loans_rmb", "对实体经济发放的外币贷款折合人民币"),
    ("entrusted_loans", "委托贷款"),
    ("trust_loans", "信托贷款"),
    ("undiscounted_bank_acceptances", "未贴现的银行承兑汇票"),
    ("corporate_bonds", "企业债券"),
    ("government_bonds", "政府债券"),
    ("nonfinancial_enterprise_equity", "非金融企业境内股票"),
]
verified = set()
originals = {}
negative = zero = trillion = hundred_million = yoy = 0
for section in re.split(r"(?=^### D\d{2} ·)", text, flags=re.M)[1:]:
    period = re.match(r"### D\d{2} · (\d{4}-\d{2}) ·", section).group(1)
    sha, length = re.search(r"SHA-256：([a-f0-9]{64})；原始字节：(\d+)", section).groups()
    location, result_index = re.search(r"读取位置：(.+?)。准备 JSON：/data/results/(\d+)/parsed/scalars", section).groups()
    source_path = Path(location)
    if not source_path.is_absolute():
        source_path = repo / source_path
    content = source_path.read_bytes()
    assert len(content) == int(length) and hashlib.sha256(content).hexdigest() == sha
    parser = Blocks()
    parser.feed(content.decode("utf-8"))
    blocks = [(line, ''.join(value.split())) for line, value in parser.blocks if value.strip()]
    paragraphs = {}
    for kind, line, position, main in re.findall(r"(S/Y|F) 正文定位 L(\d+)/P(\d+)；总量与期次原文：([^\n]+)", section):
        block_line, paragraph = blocks[int(position)-1]
        assert block_line == int(line) and paragraph.startswith(main.strip())
        head, components = paragraph.split("其中，", 1)
        parts = [head, *components.rstrip("。").split("；")]
        assert len(parts) == 9, (period, kind, parts)
        for part, (_, label) in zip(parts, mapping, strict=True):
            assert label in part
        paragraphs[kind] = parts
    result = prep["data"]["results"][int(result_index)]
    assert result["family"] == "pbc_social_financing" and result["artifact_sha256"] == sha
    scalars = result["parsed"]["scalars"]
    seen = set()
    for line in section.splitlines():
        if not re.match(r"\| C[0-8] ", line):
            continue
        fields = [item.strip() for item in line.split("|")[1:-1]]
        component_index = int(fields[0][1])
        component, _ = mapping[component_index]
        for column, cell in zip(("S", "Y", "F"), fields[1:], strict=True):
            if cell == "本篇无此列":
                continue
            literal, conversion, expected_text, prepared_text, scalar_index = re.fullmatch(
                r"([^；]+)；([^；]+) → ([^；]+)；旧 ([^（]+)（s(\d+)）；一致", cell
            ).groups()
            part = paragraphs["F" if column == "F" else "S/Y"][component_index]
            if column == "Y":
                observed = re.search(r"同比(持平|(?:增长|下降)[\d.]+%)", part).group(1)
                assert observed == literal
                if literal == "持平":
                    expected = Decimal(0)
                else:
                    direction, number = re.fullmatch(r"(增长|下降)([\d.]+)%", literal).groups()
                    expected = Decimal(number) * (-1 if direction == "下降" else 1)
                measure, field, unit, kind = "stock_yoy", "stock_yoy_pct", "percent", "month"
                yoy += 1
            else:
                amount_match = re.search(r"([\d.]+)(万亿元|亿元)", part)
                number, source_unit = amount_match.groups()
                assert number + source_unit in literal
                prefix = part[:amount_match.start()]
                if column == "F" and component_index != 0:
                    direction = re.match(r"(增加|减少|净融资|融资)", literal).group(1)
                    assert prefix.endswith(direction)
                else:
                    direction = "增加"
                expected = Decimal(number) * (10000 if source_unit == "万亿元" else 1) * (-1 if direction == "减少" else 1)
                measure = "stock_end" if column == "S" else "ytd_increment"
                field = "stock_end_trillion" if column == "S" else "ytd_increment_100m"
                unit = "hundred_million_cny"
                kind = "month" if column == "S" else "year_to_month"
                trillion += source_unit == "万亿元"
                hundred_million += source_unit == "亿元"
            assert expected == Decimal(expected_text) == Decimal(prepared_text)
            index = int(scalar_index)
            assert index not in seen
            seen.add(index)
            candidate = scalars[index]
            dimensions = {"measure": measure}
            metric = "CN_SF_TOTAL"
            if component is not None:
                dimensions["component"] = component
                metric = "CN_SF_COMPONENTS"
            assert candidate["metric_id"] == metric and candidate["dimensions"] == dimensions
            assert candidate["source_field"] == field and candidate["unit"] == unit and candidate["period_kind"] == kind
            year, month = map(int, period.split("-"))
            assert candidate["period_start"] == (f"{period}-01" if kind == "month" else f"{year}-01-01")
            assert candidate["period_end"] == f"{period}-{calendar.monthrange(year, month)[1]:02d}"
            assert Decimal(str(candidate["value"])) == expected
            identity = (metric, component, measure, period)
            assert identity not in verified
            verified.add(identity)
            negative += expected < 0
            zero += expected == 0
    assert seen == set(range(len(scalars)))
    assert sha not in originals
    originals[sha] = len(content)
assert len(originals) == 51 and sum(originals.values()) == 1609364
assert len(verified) == 837 and (negative, zero, trillion, hundred_million, yoy) == (131, 2, 390, 168, 279)
print(json.dumps({"verified_literals": 837, "originals": 51, "original_bytes": 1609364,
                  "negative_values": negative, "explicit_zero_values": zero, "trillion_conversions": trillion,
                  "hundred_million_values": hundred_million, "official_yoy_values": yoy,
                  "report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest(),
                  "local_links": len(links), "network_requests": 0, "application_parser_calls": 0,
                  "scope": "raw nonempty block line/index, named component clause, literal, identity, exact decimal normalization, scalar index, period"}, indent=2))

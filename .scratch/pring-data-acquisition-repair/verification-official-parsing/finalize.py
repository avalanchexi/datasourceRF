"""Finalize this completed batch's evidence and exact staging allowlist."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
base = here.parent
repo = base.parents[1]
logs = [
    "verification-capacity-columns-green.txt", "verification-capacity-columns-related.txt",
    "verification-capacity-duplicate-red.txt", "verification-money-units-green.txt",
    "verification-money-units-red.txt", "verification-official-parsing-related.txt",
    "verification-official-parsing-pytest-20260908-a.txt",
]
for path in [*(base / name for name in logs), *here.glob("*.txt"), *here.glob("*.json")]:
    raw = path.read_bytes()
    text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
assert "741 passed in 977.15s" in (base / logs[-1]).read_text()
result = {
    "status": "completed_code_batch", "base_commit": "ca2780710f2079d59cfb172bde314cba3f547be6",
    "passed": 741, "failed": 0, "duration_seconds": 977.15,
    "test_exit_code": 0, "full_suite_runs": 1,
    "runtime": "/home/tywin/.cache/pring-cycle/verification/repair-official-parsing-suite-20260908-a",
    "log": "../" + logs[-1], "targeted_passed": 57, "targeted_duration_seconds": 4.93,
    "new_regression_cases": 16, "installed_source_files": 81,
    "source_fingerprint": "code-fingerprint.json", "mypy_checked_files": 84,
    "ruff_exit_code": 0, "mypy_exit_code": 0, "spec_final_findings": 0,
    "standards_final_findings": 0, "review": "review.md",
    "source_certification_grants": 0, "production_writes": 0, "model_activations": 0,
    "ticket_13_execution": "in-progress", "preparation_scalar_denominator": 1858,
    "independently_literal_matching_old_preparation_scalars": 1856,
    "capacity_q1_alias_mapping_pending": 1, "old_prepared_money_numeric_discrepancies": 1,
    "money_discrepancy_fixed_in_current_parser": True,
    "not_yet_individually_audited_preparation_scalars": 0,
}
(here / "final.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
path = base / "implementation-official-parsing.md"
text = path.read_text(encoding="utf-8").replace("Execution: verification-in-progress", "Execution: completed-code-batch")
text = text.replace("本批一次全套运行中。", "本批一次全套741通过、0失败、977.15秒，退出0；全套完成后81安装Python文件再次一致。")
text += "\n[OMO全值审计](p1-omo-full-value-audit.md)及[根复核](verification-official-parsing/omo-verification.json)通过：131原件4013310字节、252格、136本地链接；10份零操作无利率列。扣除两旧锚点，最终1856/1858旧标量严格相符，1项旧M2尾差和1项Q1来源复用映射单列，未逐值检查0。旧包未修改；本批代码修复不把旧尾差改记为旧包通过。\n\n[最终验证记录](verification-official-parsing/final.json)。下一步新路径纯解析复算和认证前置整理，不创建目录、候选模型或倒填取得时间。\n"
path.write_text(text, encoding="utf-8", newline="\n")
status = base / "continuation-status.md"
text = status.read_text(encoding="utf-8")
start = text.index("最新从`d3c83e5`")
end = text.index("最新从`375950b`", start)
current = """最新从`ca278071`继续：[官方解析修复](implementation-official-parsing.md)完成：产能非Q1缺累计列及重复工业行拒绝，M1/M2原始十进制金额先换算再输出，收据版本v0004。**741全套通过、0失败、977.15秒**，57关联、16新增、Ruff/mypy84、双轴0，81安装Python文件前后匹配。[最终收据](verification-official-parsing/final.json)。

贷款279格、社融837格、OMO252格已逐值及原件/字段/单位/期次根复核。原1858标量现在全部检查：**1856严格相符、1旧M2尾差、1产能Q1累计复用映射待确认**，未检查0。M2尾差在当前v4真实原件回归已修；旧准备包保持原样。数值一致不代表首发时间、实际获取时间、来源认证或模型采用通过。

**立即续作：**保存新的只读复算准备包，继承旧包hash并记录v4与差异；未知历史时间继续未知，Q1复用单列。随后按正式来源合同前置推进，不能绕过旧v3认证阻断。业务规则、外部源缺件、真实检索配对、AI网络与120日重放仍开放。

前批[OMO无效流量修复](implementation-omo-invalid-flow.md)已提交ca278071：725全套、75关联、9新增、双轴0；已知坏流量不会被当0或跳过以回退旧净额。完全无记录、空到期集合及台账日历完整性仍需证据。

"""
status.write_text(text[:start] + current + text[end:], encoding="utf-8", newline="\n")
issue = base / "issues/13-remaining-p1-evidence.md"
text = issue.read_text(encoding="utf-8")
comment = "\n- 2026-09-08：[官方解析修复](../implementation-official-parsing.md)741全套/57关联/16新增通过，双轴0，修复非Q1累计缺列与M1/M2尾差，收据v0004。贷款279、社融837、OMO252格根复核完成；旧1858全量已审，1856相符、1旧尾差（当前代码已修）、1Q1复用源映射待定。旧包保持不变；下一步新路径纯解析准备，27项认证和模型采用仍开放。\n"
issue.write_text(text.replace("## Comments\n", "## Comments\n" + comment, 1), encoding="utf-8", newline="\n")
attrs = base / ".gitattributes"
text = attrs.read_text(encoding="utf-8")
line = "p1-omo-full-value-audit.md -text whitespace=cr-at-eol,-blank-at-eof"
if line not in text:
    attrs.write_text(text.rstrip() + "\n" + line + "\n", encoding="utf-8", newline="\n")
files = ["src/pring_cycle/official_context.py", "tests/adapters/test_rrr_context.py",
         "tests/adapters/test_capacity_column_completeness.py", "tests/adapters/test_official_money_units.py",
         "tests/fixtures/.gitattributes", "tests/fixtures/pbc_money_202602.html"]
names = [".gitattributes", "implementation-official-parsing.md", "continuation-status.md",
         "issues/13-remaining-p1-evidence.md", "money-normalization-boundary.md",
         "p1-loan-structure-full-value-audit.md", "p1-social-financing-full-value-audit.md",
         "p1-omo-full-value-audit.md", *logs]
files += [(base / name).relative_to(repo).as_posix() for name in names]
files += [path.relative_to(repo).as_posix() for path in here.iterdir() if path.is_file()]
files += [(here / name).relative_to(repo).as_posix() for name in ("commit-files.txt", "verify_staged.py")]
(here / "commit-files.txt").write_text("\n".join(sorted(set(files))) + "\n", encoding="utf-8")
print("Finalized batch evidence and exact allowlist")

"""Finalize only after the one full-suite process has returned exit code zero."""
import argparse
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--observed-test-exit-code", type=int, required=True)
args = parser.parse_args()
assert args.observed_test_exit_code == 0
here = Path(__file__).resolve().parent
base = here.parent
repo = base.parents[1]
logs = [
    "verification-history-discovery-red.txt", "verification-history-discovery-green.txt",
    "verification-history-threaded-red.txt", "verification-history-threaded-red-corrected.txt",
    "verification-history-threaded-green.txt", "verification-history-listing-limits-red.txt",
    "verification-history-receipts-related.txt", "verification-history-review-red.txt",
    "verification-history-browser-red-corrected.txt", "verification-history-review-green.txt",
    "verification-history-receipts-final-related.txt",
    "verification-history-receipts-pytest-20260908-a.txt",
]
for path in [*(base / name for name in logs), *here.glob("*.txt"), *here.glob("*.json")]:
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    path.write_text(raw.decode(encoding).replace("\r\n", "\n"), encoding="utf-8", newline="\n")
log = (base / logs[-1]).read_text(encoding="utf-8")
matches = re.findall(r"^(\d+) passed in ([\d.]+)s", log, re.M)
assert len(matches) == 1 and matches[0][0] == "756"
assert not re.search(r"\d+ failed|\d+ error", log)
duration = float(matches[0][1])
result = {
    "status": "completed_code_batch", "base_commit": "a569fd757c7d19a4ae95b980bd2b1c0c51cba973",
    "passed": 756, "failed": 0, "duration_seconds": duration,
    "test_exit_code": args.observed_test_exit_code, "full_suite_runs": 1,
    "runtime": "/home/tywin/.cache/pring-cycle/verification/repair-history-receipts-suite-20260908-a",
    "log": "../" + logs[-1], "targeted_passed": 70, "targeted_duration_seconds": 51.62,
    "new_regression_cases": 15, "installed_source_files": 81,
    "source_fingerprint": "code-fingerprint.json", "mypy_checked_files": 82,
    "ruff_exit_code": 0, "mypy_exit_code": 0, "spec_initial_findings": 4,
    "spec_final_findings": 0, "standards_final_findings": 0, "review": "review.md",
    "source_certification_grants": 0, "production_writes": 0, "model_activations": 0,
    "new_live_network_requests": 0, "ticket_13_execution": "in-progress",
}
(here / "final.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
path = base / "implementation-history-receipts.md"
text = path.read_text(encoding="utf-8").replace("Execution: verification-in-progress", "Execution: completed-code-batch")
text = text.replace("本批一次全套运行中。", f"本批一次全套756通过、0失败、{duration}秒，退出0；完成后81安装Python文件再次核对一致。[最终记录](verification-history-receipts/final.json)。")
path.write_text(text, encoding="utf-8", newline="\n")
status = base / "continuation-status.md"
text = status.read_text(encoding="utf-8")
entry = f"\n从`a569fd7`继续：[历史smoke收据补齐](implementation-history-receipts.md)完成，756全套/70关联/15新增通过，全套{duration}秒，双轴复审0，Ruff/mypy82及81安装源指纹一致。目录/正文、线程owner、目标日、禁止自动重定向、错误体有界前缀和browser原包装转换血缘均验收。与03已修的history导入分别留证，不恢复过去SYSTEM或授予历史PUBLIC。\n"
text = text.replace("## 已实际完成的本轮交付\n", "## 已实际完成的本轮交付\n" + entry, 1)
text = text.replace("并核查历史smoke发现/下载是否遗漏真实逐请求回执", "继续票19的前置与可独立实施边界核对")
status.write_text(text, encoding="utf-8", newline="\n")
issue = base / "issues/13-remaining-p1-evidence.md"
text = issue.read_text(encoding="utf-8")
entry = f"\n- 2026-09-08：[历史smoke收据修复](../implementation-history-receipts.md)756全套/{duration}秒、70关联、15新增、双轴复审0；发现目录及线程正文请求保留实际回执，browser原包装与HTML分别留证，目标日/owner/重定向/错误体上限明确。[新A18准备包](../p1-official-preparation-v2.md)已提交a569fd7，但仍不构成27项认证或真实模型采用。\n"
issue.write_text(text.replace("## Comments\n", "## Comments\n" + entry, 1), encoding="utf-8", newline="\n")
attrs = base / ".gitattributes"
text = attrs.read_text(encoding="utf-8")
for line in (
    "source-history-receipt-boundary.md -text whitespace=cr-at-eol,-blank-at-eof",
    "ticket19-implementation-boundary.md -text whitespace=cr-at-eol,-blank-at-eof",
    "verification-history-*.txt whitespace=-blank-at-eol",
    "verification-history-receipts/*.txt whitespace=-blank-at-eol",
):
    if line not in text:
        text = text.rstrip() + "\n" + line + "\n"
attrs.write_text(text, encoding="utf-8", newline="\n")
files = ["src/pring_cycle/acquisition.py", "src/pring_cycle/source_history.py",
         "tests/adapters/test_source_history_acquisition.py", "tests/fixtures/.gitattributes",
         "tests/fixtures/pbc_social_financing_202501.html", "tests/fixtures/nbs_gdp_2023q4.html"]
names = [".gitattributes", "continuation-status.md", "issues/13-remaining-p1-evidence.md",
         "implementation-history-receipts.md", "source-history-receipt-boundary.md",
         "ticket19-implementation-boundary.md", *logs]
files += [(base / name).relative_to(repo).as_posix() for name in names]
files += [path.relative_to(repo).as_posix() for path in here.iterdir() if path.is_file()]
files += [(here / name).relative_to(repo).as_posix() for name in ("commit-files.txt", "verify_staged.py")]
(here / "commit-files.txt").write_text("\n".join(sorted(set(files))) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result))

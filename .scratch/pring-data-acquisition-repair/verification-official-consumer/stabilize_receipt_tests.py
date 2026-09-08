"""One-time explicit clock opt-ins for the statically reviewed default-capture paths."""
import ast
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
selected = {
    "tests/adapters/test_source_history_acquisition.py": None,
    "tests/integration/test_treasury_csv_acquisition.py": None,
    "tests/integration/test_eia_html_acquisition.py": None,
    "tests/integration/test_core_history_refresh.py": {60, 119, 149, 275, 309, 354, 397, 438},
    "tests/integration/test_context_acquisition_receipts.py": {35, 55, 97, 131, 225, 253, 301, 393, 448, 504, 571, 592, 622, 697, 730},
    "tests/integration/test_gdp_semantics.py": {24, 90},
    "tests/integration/test_futures_warrant_completeness.py": {15, 72},
    "tests/integration/test_p2_source_timing.py": {18},
    "tests/adapters/test_source_history.py": {10},
    "tests/adapters/test_official_context.py": {300},
    "tests/integration/test_full_run_retrieval.py": {33, 105, 360, 447, 608, 673, 719, 882, 970, 1046},
    "tests/integration/test_worker_execution.py": {239, 315, 447, 795},
}
output = Path(__file__).with_name("clock-opt-ins.json")
assert not output.exists()
changes = []
# Validate the complete allowlist before writing any file.
for relative, numbers in selected.items():
    path = root / relative
    original = path.read_bytes()
    source = original.decode("utf-8")
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith("test_") and (numbers is None or node.lineno in numbers)]
    if numbers is not None:
        assert {node.lineno for node in functions} == numbers, relative
    picked = [node for node in functions
              if not {arg.arg for arg in node.args.args} & {"acquisition_clock", "runtime_clock"}]
    lines = source.splitlines(keepends=True)
    for node in sorted(picked, key=lambda n: n.lineno, reverse=True):
        lines.insert(node.lineno - 1, '@pytest.mark.usefixtures("runtime_clock")\n')
    updated = "".join(lines)
    if not any(isinstance(node, ast.Import) and any(alias.name == "pytest" for alias in node.names)
               for node in tree.body):
        assert not source.startswith("from __future__"), relative
        updated = "import pytest\n\n" + updated
    ast.parse(updated)
    changes.append((path, updated.encode("utf-8"), {
        "path": relative, "sha256_before": hashlib.sha256(original).hexdigest(),
        "functions": [node.name for node in picked],
    }))
for path, updated, record in changes:
    path.write_bytes(updated)
    record["sha256_after"] = hashlib.sha256(updated).hexdigest()
output.write_text(json.dumps({"operation": "explicit_function_scoped_test_clock_opt_ins",
                             "production_changes": 0, "files": [r for _, _, r in changes]},
                            indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(changes), "functions": sum(len(r["functions"]) for _, _, r in changes)}))

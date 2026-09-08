"""Explicit clock opt-ins for search paths that call the shared receipt boundary."""
import ast
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
output = Path(__file__).with_name("search-clock-opt-ins.json")
assert not output.exists()
records = []
for relative, excluded in {
    "tests/integration/test_search_evidence.py": {
        "test_unknown_publication_window_is_distinct_from_not_yet_released",
        "test_local_lpr_requires_both_reported_tenors",
    },
    "tests/integration/test_retrieval_ledger.py": {
        "test_existing_unexpired_negative_cache_survives_new_ledger",
    },
}.items():
    path = root / relative
    original = path.read_bytes()
    source = original.decode("utf-8")
    tree = ast.parse(source)
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name.startswith("test_") and node.name not in excluded]
    assert '@pytest.mark.usefixtures("runtime_clock")' not in source
    lines = source.splitlines(keepends=True)
    for node in sorted(nodes, key=lambda n: n.lineno, reverse=True):
        lines.insert(node.lineno - 1, '@pytest.mark.usefixtures("runtime_clock")\n')
    updated = "".join(lines).encode("utf-8")
    ast.parse(updated)
    path.write_bytes(updated)
    records.append({"path": relative, "functions": [node.name for node in nodes],
                    "sha256_before": hashlib.sha256(original).hexdigest(),
                    "sha256_after": hashlib.sha256(updated).hexdigest()})
output.write_text(json.dumps({"files": records, "production_changes": 0}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(records), "functions": sum(len(r["functions"]) for r in records)}))

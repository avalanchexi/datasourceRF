"""One-off mechanical signature update for existing legacy test doubles."""
import ast
from pathlib import Path

for name in (
    "tests/integration/test_context_projection.py",
    "tests/integration/test_rehearsal_cutover.py",
    "tests/evidence/test_point_in_time.py",
):
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    changes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "certified_definition":
            assert node.end_lineno is not None
            block = "".join(lines[node.lineno - 1:node.end_lineno])
            if "database_path:" not in block:
                block = block.replace(
                    '        definition_version: str = "metric-catalog-v0002",\n',
                    '        definition_version: str = "metric-catalog-v0002",\n'
                    '        database_path: Path | None = None,\n',
                )
            assert "database_path:" in block
            block = block.replace(
                "definition_version=definition_version,\n",
                "definition_version=definition_version,\n            database_path=database_path,\n",
            ).replace(
                "definition_version=definition_version)",
                "definition_version=definition_version, database_path=database_path)",
            )
            changes.append((node.lineno - 1, node.end_lineno, block))
    for start, end, block in sorted(changes, reverse=True):
        lines[start:end] = [block]
    text = "".join(lines)
    text = text.replace(
        'lambda metric_id, *, definition_version="metric-catalog-v0002": replace(\n'
        '            metric_definition(metric_id, definition_version=definition_version),',
        'lambda metric_id, *, definition_version="metric-catalog-v0002", database_path=None: replace(\n'
        '            metric_definition(metric_id, definition_version=definition_version, database_path=database_path),',
    )
    path.write_bytes(text.encode())
    print(name, len(changes))

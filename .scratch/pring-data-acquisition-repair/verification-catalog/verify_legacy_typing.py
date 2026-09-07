"""Compare expanded legacy typing diagnostics against the fixed source baseline."""
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
base = "0679a4758316bbeb520da9d79aafeb7572f5c6ce"
names = ["tests/integration/test_context_projection.py",
         "tests/integration/test_rehearsal_cutover.py", "tests/evidence/test_point_in_time.py"]
scratch = root / ".tmp/catalog-legacy-typing-20260908"
scratch.mkdir(parents=True, exist_ok=True)
baseline = []
for name in names:
    path = scratch / Path(name).name
    content = subprocess.check_output(["git", "show", f"{base}:{name}"])
    if path.exists():
        assert path.read_bytes() == content
    else:
        path.write_bytes(content)
    baseline.append(str(path))

def check(paths: list[str]) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "src/pring_cycle", "tests/models/test_candidate_admission.py",
         *paths, "--cache-dir", "/home/tywin/.cache/pring-cycle/verification/catalog-mypy-01"],
        capture_output=True, text=True, check=False,
    )
    errors = sorted(
        (Path(match[1]).name, match[2])
        for match in re.finditer(r"^(.+?):\d+: error: (.+)$", result.stdout, re.MULTILINE)
    )
    return {"exit_code": result.returncode, "errors": errors, "output": result.stdout}

old = check(baseline)
current = check(names)
assert old["errors"] == current["errors"], (old, current)
assert old["exit_code"] == current["exit_code"] == 1
document = {"baseline": base, "legacy_diagnostics_unchanged": True,
            "baseline_result": old, "current_result": current}
Path(__file__).with_name("legacy-typing.json").write_text(json.dumps(document, indent=2) + "\n")
print(json.dumps({"legacy_diagnostics_unchanged": True, "error_count": len(old["errors"])}))

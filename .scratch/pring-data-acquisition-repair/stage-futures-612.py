"""Stage verified ticket 11 software and its own records, preserving older WIP."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
acceptance = json.loads((BASE / 'verification-futures-acceptance-611.json').read_bytes())
assert acceptance['status'] == 'passed' and acceptance['scope'] == 'ticket11_software_only'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == acceptance['base_head']
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT)
preview = acceptance['independent_head_plus_own_delta']
patch = BASE / preview['patch']
assert hashlib.sha256(patch.read_bytes()).hexdigest() == preview['patch_sha256']
subprocess.run(['git', 'apply', '--cached', '--check', str(patch)], cwd=ROOT, check=True)
subprocess.run(['git', 'apply', '--cached', str(patch)], cwd=ROOT, check=True)
owned = {item['path'] for item in preview['files']}
assert set(subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, text=True).splitlines()) == owned
for item in preview['files']:
    assert hashlib.sha256(subprocess.check_output(['git', 'show', ':' + item['path']], cwd=ROOT)).hexdigest() == item['sha256']

def head_text(path):
    return subprocess.check_output(['git', 'show', 'HEAD:' + path.relative_to(ROOT).as_posix()], cwd=ROOT, text=True)

def index_text(path, text):
    digest = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'], cwd=ROOT, input=text.encode()).decode().strip()
    subprocess.run(['git', 'update-index', '--cacheinfo', '100644,' + digest + ',' + path.relative_to(ROOT).as_posix()], cwd=ROOT, check=True)

summary = ('票11软件输入路径通过[611根核验](verification-futures-acceptance-611.json)：'
           + acceptance['tests']['public-order-green-607'] + '（家族）；'
           + acceptance['tests']['related-610'] + '（三个既有相关文件）；'
           + acceptance['independent_tests'] + '（独立HEAD加本票三文件增量）。'
           '各范围分别留证，不相加当默认全套；类型、Ruff/格式及608两轴通过，保留两项非阻断P3维护建议。'
           '公开采集、既存原件后审关联、双点时输入查询和修订/冲突/缺件/恢复已验证；'
           '审查或元数据更新不会抬高旧价格的版本顺序。'
           '真实PP、历史PUBLIC/时段/许可认证仍开放，11整体Execution保持blocked。'
           '下一项12选约与商品两项注册合同；15项市场P1仍为13项软件路径，M3–M6、容量和最终默认全套未完成，23延期。')
issue = BASE / 'issues/11-futures-contract-evidence.md'
current = issue.read_text()
heading = '### 2026-09-12 日历选约输入纵向验收'
start, end = current.index(heading), current.index('## Testing decisions')
section = current[start:end].replace('- [ ]', '- [x]')
assert section.count('- [x]') == 2
section += '上述两项仅验收软件协议和明确标记的隔离输入；原五项真实输入/官方证据与认证条件保持未勾选。\n\n'
comment = '\n- 2026-09-13 批611/612：两项新增软件AC完成，见[实施记录](../implementation-11-futures-inputs.md)、[输入消费协议](../futures-input-consumer-contract.md)及[根核验](../verification-futures-acceptance-611.json)。公开后审绑定与SYSTEM/PUBLIC修订排序均经实际RED/GREEN及复审，608 Spec剩余0/Standards硬违规0，保留两项非阻断P3建议。真实来源认证仍blocked，接续12，不结束完整实施目标。\n'
issue.write_text(current[:start] + section + current[end:] + comment)
issue_index = head_text(issue)
assert heading not in issue_index
issue_index = issue_index.replace('## Testing decisions', section + '## Testing decisions', 1) + comment
index_text(issue, issue_index)

entry = BASE / 'continuation-status.md'
new_prefix = '## 票11软件验收611完成 / 接续12\n\n' + summary + '\n\n'
entry.write_text(new_prefix + entry.read_text())
index_text(entry, new_prefix + head_text(entry))
implementation = BASE / 'implementation-11-futures-inputs.md'
implementation.write_text(implementation.read_text() + '\n## 软件验收611/612\n\n' + summary + '\n\n仅提交独立验证的三文件增量和本票记录，旧工作区修改保持原样。源确认与固定120日真实验收不由这些合成控制授予。\n')
all_tasks = BASE / 'implementation-all-tasks-20260913.md'
old = '下一项11输入→12商品2项的家族合同及派生行为。'
new = '11输入软件已完成：607家族70项、610相关文件及609独立HEAD增量通过，608两轴与611根核验通过；已审时间后补和双点时源版本顺序分开。下一项12商品2项的家族合同及派生行为，真实来源认证继续开放。'
assert old in all_tasks.read_text() and old in head_text(all_tasks)
all_tasks.write_text(all_tasks.read_text().replace(old, new, 1))
index_text(all_tasks, head_text(all_tasks).replace(old, new, 1))

artifacts = {implementation, BASE / 'futures-input-consumer-contract.md', Path(__file__).resolve()}
prefixes = ('verification-futures-', 'review-futures-', 'prepare-futures-', 'run-futures-', 'verify-futures-', 'futures-base-', 'futures-baseline-', 'futures-index-preview-', 'futures-preview-preparation-', 'research-pp-official-route-')
for path in BASE.iterdir():
    if not path.is_file() or not path.name.startswith(prefixes):
        continue
    match = re.search(r'(?:^|-)(\d{3,})(?:-|\.|$)', path.name)
    if match and 535 <= int(match.group(1)) <= 612:
        artifacts.add(path)
for directory in BASE.glob('futures-review-*'):
    if directory.is_dir() and directory.name.rsplit('-', 1)[-1].isdigit() and 535 <= int(directory.name.rsplit('-', 1)[-1]) <= 608:
        artifacts.update(path for path in directory.iterdir() if path.is_file())
for path in artifacts:
    assert not path.is_symlink()
subprocess.run(['git', 'add', '--', *sorted(path.relative_to(ROOT).as_posix() for path in artifacts)], cwd=ROOT, check=True)
expected = owned | {path.relative_to(ROOT).as_posix() for path in artifacts | {issue, entry, all_tasks}}
actual = set(subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, text=True).splitlines())
assert actual == expected
for item in preview['files']:
    assert hashlib.sha256(subprocess.check_output(['git', 'show', ':' + item['path']], cwd=ROOT)).hexdigest() == item['sha256']
subprocess.run(['git', 'diff', '--cached', '--check', '--', *sorted(owned)], cwd=ROOT, check=True)
blobs = {}
for line in subprocess.check_output(['git', 'ls-files', '--stage', '--', *sorted(actual)], cwd=ROOT, text=True).splitlines():
    metadata, name = line.split('\t', 1)
    mode, digest, stage = metadata.split()
    assert stage == '0'
    blobs[name] = {'mode': mode, 'blob': digest}
assert set(blobs) == actual
report = {'status': 'ready_to_commit', 'base_head': acceptance['base_head'], 'staged_paths': sorted(actual), 'staged_blobs': blobs, 'source_files': preview['files'], 'old_worktree_changes_preserved': True}
with (BASE / 'futures-index-audit-612.json').open('x') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
print(json.dumps({'status': report['status'], 'staged_files': len(actual), 'source_files': len(owned)}))

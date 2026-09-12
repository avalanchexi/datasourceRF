"""Stage the accepted amount slice while preserving older worktree changes."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
acceptance = json.loads((BASE / 'verification-amount-acceptance-534.json').read_text())
assert acceptance['status'] == 'passed'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == acceptance['base_head']
preview = json.loads((BASE / 'amount-preview-preparation-531.json').read_text())
owned = {item['path'] for item in preview['files']}
assert set(subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True).splitlines()) == owned
for item in preview['files']:
    assert hashlib.sha256(subprocess.check_output(['git', 'show', ':' + item['path']])).hexdigest() == item['sha256']

def head_text(path):
    return subprocess.check_output(['git', 'show', 'HEAD:' + path.relative_to(ROOT).as_posix()]).decode()

summary = '''票10软件切片已通过：[根核验534](verification-amount-acceptance-534.json)绑定321输入/4保护、最终源码与环境、实际终态及独立八文件补丁。530金额家族28项通过，532相关263项通过；531独立HEAD加本票增量203项通过，根类型95/独立92、Ruff/格式及两轴530/533通过。三个测试范围分别留证，不合计为默认全套。全池分子/分母、未知金额、覆盖排重、PUBLIC及原件恢复保持可复核；真实盘后补证、官方差额与来源认证仍开放。市场15项P1已有13项软件路径，下一步11真实月份合约输入→12商品两项；09全市场容量、M3–M6及最终默认全套继续推进，23延期。'''
issue = BASE / 'issues/10-breadth-amount-share.md'
current = issue.read_text()
heading = '### 2026-09-12 全范围金额新目录纵向验收'
section = current[current.index(heading):current.index('## Testing decisions')].replace('- [ ]', '- [x]')
assert section.count('- [x]') == 2
old_section = current[current.index(heading):current.index('## Testing decisions')]
current = current.replace(old_section, section, 1)
if 'Execution:' not in current:
    current = current.replace('Status: ready-for-agent\n', 'Status: ready-for-agent\nExecution: blocked\n', 1)
comment = '\n- 2026-09-13 批534：仅新增两项软件AC完成；28家族、263相关与203独立分别通过，两轴530/533无新增问题，类型/Ruff通过。见[软件实施](../implementation-10-registered-amount-breadth.md)及[根核验534](../verification-amount-acceptance-534.json)。原五项真实口径/补证/差额及认证条件继续开放，不以合成例关闭整票。\n'
current += comment
issue.write_text(current)
# Index only this issue's software section and current conclusion.
issue_index = head_text(issue).replace('Status: ready-for-agent\n', 'Status: ready-for-agent\nExecution: blocked\n', 1)
issue_index = issue_index.replace('## Testing decisions', section + '## Testing decisions', 1) + comment

entry = BASE / 'continuation-status.md'
current = entry.read_text()
new_prefix = '## 票10软件验收534完成\n\n' + summary + '\n\n'
entry.write_text(new_prefix + current[current.index('## 票09提交501'):])
entry_index = new_prefix + head_text(entry)
implementation = BASE / 'implementation-10-registered-amount-breadth.md'
implementation.write_text(implementation.read_text() + '\n\n## 软件验收534\n\n' + summary + '\n\n只勾票10新增两项软件AC，原五项真实验收保持开放。索引只接纳独立531的八文件和明确列出的本票材料；源码中的旧工作区增量保持原样。\n')
all_tasks = BASE / 'implementation-all-tasks-20260913.md'
current = all_tasks.read_text()
old = '当前15项P1已有12项软件路径，真实历史池/事件/PUBLIC及全市场容量仍开放。下一项10金额1项及11→12商品2项的家族合同、输入及派生行为。'
new = '10金额软件也完成：530家族28项、532相关263项、531独立HEAD203项通过，类型/Ruff及两轴530/533通过，534根核验通过。当前15项P1已有13项软件路径，真实历史池/事件/PUBLIC及全市场容量仍开放。下一项11输入→12商品2项的家族合同及派生行为。'
assert old in current
all_tasks.write_text(current.replace(old, new, 1))
patterns = ('amount-*.json','amount-*.patch','amount-*.txt','amount-*.md','run-amount-*.py','prepare-amount-*.py','verify-amount-*.py','stage-amount-*.py','verification-amount-*','review-amount-*','implementation-10-registered-amount-breadth.md','research-10-software-inputs-485.md')
artifacts = {p for pattern in patterns for p in BASE.glob(pattern) if p.is_file()}
artifacts.add(all_tasks)
for path in artifacts:
    assert not path.is_symlink()
subprocess.run(['git', 'add', '--', *sorted(p.relative_to(ROOT).as_posix() for p in artifacts)], check=True)
for path, value in ((issue, issue_index), (entry, entry_index)):
    digest = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'], input=value.encode()).decode().strip()
    subprocess.run(['git', 'update-index', '--cacheinfo', '100644,' + digest + ',' + path.relative_to(ROOT).as_posix()], check=True)
expected = owned | {p.relative_to(ROOT).as_posix() for p in artifacts | {issue, entry}}
actual = set(subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True).splitlines())
assert actual == expected
for item in preview['files']:
    assert hashlib.sha256(subprocess.check_output(['git', 'show', ':' + item['path']])).hexdigest() == item['sha256']
subprocess.run(['git', 'diff', '--cached', '--check', '--', *sorted(owned)], check=True)
audit = BASE / 'amount-index-audit-534.json'
assert not audit.exists()
audit.write_text(json.dumps({'status':'ready_to_commit','base_head':acceptance['base_head'],'staged_paths':sorted(actual),'source_files':preview['files'],'old_worktree_changes_preserved':True}, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'status':'ready_to_commit','staged_files':len(actual),'source_files':len(owned)}))

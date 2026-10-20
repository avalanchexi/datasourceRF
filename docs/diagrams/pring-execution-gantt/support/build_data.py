"""Collect a frozen, source-backed execution-window dataset (not a timesheet)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/diagrams/pring-execution-gantt.gantt.json"
HEAD = "99c495a217b66d4bca9d6ceae4688ee69d4382bb"
SNAPSHOT = "2026-09-09T10:02:38+08:00"
REPAIR = ".scratch/pring-data-acquisition-repair/"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def commit(ref: str) -> dict:
    full, when, subject = git("show", "-s", "--format=%H%n%cI%n%s", ref).split("\n", 2)
    return {"hash": full, "short": full[:7], "committed_at": when, "subject": subject}


# Sources are implementation evidence. A completed software batch is never a
# claim that its entire parent issue, data certification, or rollout is done.
rows = [
    ("audit", "来源审查与驾驶舱修复", "07195d0", "42da5c7", ".scratch/pring-cycle-dashboard/closeout-2026-09-05.md", "暂停未闭合来源；修复暂停提示、任务入队与证据时间链接。", "352 项测试；离线验收与恢复记录。"),
    ("audit", "融资候选与广度输入补证", "42da5c7", "6edf0cb", ".scratch/pring-cycle-dashboard/source-resolution-2026-09-05.md", "保留沪深北融资候选与广度原件；用官方停牌证据裁决冲突。", "410 项测试；输入通过不等于 PUBLIC 认证。"),
    ("foundation", "修复规格与 22 票发布", "6edf0cb", "aeb6b41", REPAIR + "spec.md", "固定数据可信性、搜索补缺、模型与报告验收范围。", "规格和依赖已发布；业务规则仍逐家族收口。"),
    ("foundation", "候选持续天数纠正", "aeb6b41", "074dea6", REPAIR + "implementation-01.md", "新模型显示实际候选持续日，保留旧模型语义。", "票 01 Execution: completed。"),
    ("foundation", "核心及上下文采集收据", "074dea6", "3231539", REPAIR + "implementation-03.md", "保存请求原件、校验时钟和双点时；未知公开时间保持未知。", "票 02、03 Execution: completed。"),
    ("retrieval", "检索账本与预算恢复", "3231539", "8a343e0", REPAIR + "implementation-15.md", "逐次外部请求持久计量，保留中断与重试记录。", "票 15 Execution: completed。"),
    ("retrieval", "搜索候选到模型输入", "8a343e0", "2e08e18", REPAIR + "implementation-16.md", "搜索候选经过来源、字段与目标模型输入校验。", "票 16 软件闭环完成；真实模型补齐率另验。"),
    ("retrieval", "CLI 报告协议修复", "2e08e18", "94a16a1", REPAIR + "implementation-18.md", "区分真实 CLI 错误、解释验收和确定性降级。", "协议修复；真实合格 AI 输出仍缺。"),
    ("retrieval", "完整运行按缺口补采", "94a16a1", "02a5cce", REPAIR + "implementation-17.md", "完整运行复用检索账本，冻结 cutoff 后校验实际采用。", "票 17 Execution: completed。"),
    ("macro", "GDP、EIA 与美债候选接入", "02a5cce", "9aaf526", REPAIR + "implementation-14-treasury.md", "修正 GDP 语义，接入 EIA HTML 与 Treasury CSV 候选。", "639 项全套通过；不授予真实 P2 认证。"),
    ("macro", "派生资格、RRR 范围与库存期次", "9aaf526", "ad86bd0", REPAIR + "implementation-13-inventory-period.md", "修复未认证父项、降准双范围和错统计期输入。", "664 → 677 → 680 项全套逐批通过。"),
    ("macro", "鲜度、贷款跨年与 OMO 缺值", "ad86bd0", "ca27807", REPAIR + "implementation-omo-invalid-flow.md", "旧派生不冒充 current；一月累计差分独立；坏投放不当零。", "702 → 716 → 725 项全套逐批通过。"),
    ("macro", "官方表格与金额换算", "ca27807", "6341dd2", REPAIR + "implementation-official-parsing.md", "产能缺列、重复工业行与货币金额精度校验。", "741 项全套通过。"),
    ("catalog", "历史原件与请求收据", "6341dd2", "1cd2c00", REPAIR + "implementation-history-receipts.md", "补全历史发现、正文获取和失败原件的物理请求记录。", "756 项全套通过。"),
    ("catalog", "认证包准入与不可变目录登记", "1cd2c00", "656eaa0", REPAIR + "implementation-19-catalog.md", "先核验正式包与引用，再登记新目录并接通 LPR。", "806 → 819 项全套通过；真实完整候选未建立。"),
    ("catalog", "常规宏观新目录消费", "656eaa0", "0452aca", REPAIR + "implementation-19-official-consumption.md", "接通官方宏观数据在登记目录下的选值和采用。", "855 通过 / 1 超时；单例复测通过，保留原失败。"),
    ("discovery", "DR007 / Shibor 新目录接入", "0452aca", "087b9a8", REPAIR + "implementation-19-interbank-consumption.md", "精确绑定渠道、期限、单位、日期和实际 API 字段。", "156 项关联回归通过。"),
    ("discovery", "搜索目录绑定修复", "087b9a8", "7a7e384", REPAIR + "implementation-19-search-catalog.md", "检索、缓存和预算解析绑定实际登记目录。", "213 项关联回归通过。"),
    ("discovery", "四缺口 Tavily / Exa 实测", "7a7e384", "c062d76", REPAIR + "search-preexperiment-report.md", "真实 8 次搜索、12 次 GET；取得央行降准原通知。", "原文补齐 Tavily 1/4、Exa 0/4；模型可用率未评估。"),
    ("rrr", "降准来源入库", "c062d76", "40accae", REPAIR + "implementation-19-rrr-source.md", "接通官方 RRR 来源合同；保留两个机构范围。", "178 项关联 + 最终 8 项通过；磁盘故障后恢复。"),
    ("rrr", "完整公告选值与回放", "40accae", "d68fe6e", REPAIR + "implementation-19-rrr-members.md", "缺成员不得采用；排除版本 ID 和行顺序造成的假差异。", "246 项关联；最后 41 项回归通过。"),
    ("warrants", "仓单原行与精确收据绑定", "d68fe6e", "b640610", REPAIR + "implementation-19-warrants-source.md", "按品种、仓库和字段匹配原始行；重复身份整批拒绝。", "190 项关联；最后 12 项通过。"),
    ("warrants", "多仓库完整性与双点时消费", "b640610", "96964cf", REPAIR + "implementation-19-warrants-members.md", "原件中的空当值仍计入分母；不混合旧、新交付仓库。", "238 项关联；最后 12 项通过。"),
    ("warrants", "八品种定向补采", "96964cf", "b8cf9b3", REPAIR + "implementation-19-warrants-targeted.md", "正常八次请求；重试分别记账，中途失败不写部分声明。", "91 项关联；最后 3 项通过。"),
    ("warrants", "120 日完整仓库覆盖", "b8cf9b3", "159a725", REPAIR + "implementation-19-warrants-history.md", "每品种按完整仓库日计数；保留 120 日内至少 114 日规则。", "219 项关联通过；真实来源认证仍待完成。"),
    ("core", "三核心新目录采集", "159a725", "4084834", REPAIR + "implementation-19-core-source.md", "股票、债券、NHII 的日期、代码、价格与原件逐次核验。", "252 项关联；最后 17 项通过。"),
    ("core", "核心回放逐日 PUBLIC 修复", "4084834", "dd744ff", REPAIR + "implementation-21-core-public-replay.md", "晚公开修订不改变早期判断；不能隐藏缺失日缩短窗口。", "269 项关联；最终 23 项含合成性能测试通过。"),
    ("core", "模型使用时复核核心原件", "dd744ff", "0c33710", REPAIR + "implementation-19-core-original-consumption.md", "消费前重新核原件；缺失、损坏及多关联一坏均拒绝。", "328 项关联回归通过。"),
    ("replay", "候选状态与回放明细持久化", "0c33710", "6662bc2", REPAIR + "implementation-21-candidate-replay.md", "每日候选方向、持续天数与差异保存；旧记录不补造明细。", "342 项关联通过；追加式存档与 0020 迁移。"),
    ("replay", "上下文逐日历史与版本绑定", "6662bc2", "3e1b7d3", REPAIR + "implementation-21-context-replay.md", "保存完整上下文与可见输入历史；同值新版本也改变证据指纹。", "432 项关联通过；0021 迁移保留旧记录。"),
    ("integrity", "核心 / 仓单制品与 SQLite 连接", "3e1b7d3", "bda795f", REPAIR + "implementation-database-connections.md", "核对原件与标准化语义；修复连接依赖垃圾回收导致句柄耗尽。", "失败 1022/6/1 → 修复后默认全套 1031 项通过。"),
    ("context", "LPR 全链消费与发布日历", "bda795f", "99c495a", REPAIR + "implementation-19-context-normalized-consumption.md", "校验经济字段与时间；分别处理 PUBLIC / SYSTEM 日历和坏版本回放。", "376 项关联；默认全套 1053 项通过。"),
]

groups = [
    ("audit", "来源审查与驾驶舱 QA", "来源边界重新收口"),
    ("foundation", "规格、候选天数与收据", "22 票修复计划启动"),
    ("retrieval", "检索、预算与完整运行", "报告协议同步修复"),
    ("macro", "宏观候选与派生纠错", "资格 / 期次 / 鲜度 / 金额"),
    ("catalog", "不可变目录与候选准入", "校验先于新目录采用"),
    ("discovery", "市场传导与搜索实测", "真实搜索结果单独计量"),
    ("rrr", "降准公告完整消费", "多范围与回放一致性"),
    ("warrants", "仓单全链与历史覆盖", "原行 → 仓库 → 120 日"),
    ("core", "三核心采集与逐日回放", "修订不回写早期判断"),
    ("replay", "候选与上下文回放存档", "逐日结果可查询、可追溯"),
    ("integrity", "制品一致性与连接释放", "全套失败后定位并修复"),
    ("context", "LPR 收口 · PMI 正在推进", "从宏观原件到实际采用"),
]

tasks = []
source_index = {}
for i, (group, title, base, end, source, summary, verification) in enumerate(rows):
    start_commit, end_commit = commit(base), commit(end)
    assert git("merge-base", "--is-ancestor", end, HEAD) == ""
    raw = subprocess.check_output(["git", "show", f"{HEAD}:{source}"], cwd=ROOT)
    source_index[source] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "revision": HEAD}
    tasks.append({
        "id": f"task-{i+1:02}", "group": group, "title": title,
        "start": start_commit["committed_at"], "end": end_commit["committed_at"],
        "start_basis": "实施基点或前一相关提交；用于表示记录窗口，不是精确开工时间",
        "base_commit": start_commit, "end_commit": end_commit,
        "status": "completed", "summary": summary, "verification": verification,
        "source": source,
    })

# Freeze the observed, uncommitted PMI state. Do not chase another session's edits.
wip_source = REPAIR + "implementation-19-macro-normalized-consumption.md"
wip_raw = (ROOT / wip_source).read_bytes()
source_index[wip_source] = {"sha256": hashlib.sha256(wip_raw).hexdigest(), "bytes": len(wip_raw), "revision": "working-tree-snapshot"}
tasks.append({"id": "task-pmi", "group": "context", "title": "PMI 原件、声明与派生消费核验", "start": commit(HEAD)["committed_at"], "end": SNAPSHOT,
    "start_basis": "前一已验收 LPR 提交；截至本次观察", "base_commit": commit(HEAD), "end_commit": None,
    "status": "active", "summary": "已覆盖损坏制品、哈希自洽错值、错误声明值及回退旧统计期；字段、时间与回放边界继续推进。",
    "verification": "最近记录 6 项针对回归通过；本批未提交，未完成扩大回归和最终验收。", "source": wip_source})

group_data = []
for gid, label, note in groups:
    members = [t for t in tasks if t["group"] == gid]
    group_data.append({"id": gid, "label": label, "note": note, "start": min(t["start"] for t in members), "end": max(t["end"] for t in members),
                       "status": "active" if any(t["status"] == "active" for t in members) else "completed", "task_ids": [t["id"] for t in members]})

pending = [
    {"title": "宏观消费校验", "status": "active", "description": "完成 PMI，再覆盖 CPI、其他宏观、DR007/Shibor、RRR 多收据及派生实际采用。", "source": REPAIR + "issues/19-immutable-candidate-catalog.md"},
    {"title": "来源认证与业务规则", "status": "blocked", "description": "核心历史公开时间、北交所、CNY030、估值 / 股票池 / 完整金额、PP 等仍缺件；估值、广度和商品规则未冻结。", "source": REPAIR + "business-decisions-draft.md"},
    {"title": "真实候选与 120 日验收", "status": "pending", "description": "新完整候选、2026-03-09 至 08-28 的实际 120 中国交易日回放、当前目标日 Worker 完整运行。", "source": REPAIR + "issues/21-public-replay-120d.md"},
    {"title": "搜索、报告与正式切换", "status": "blocked", "description": "模型可用搜索补齐率未验收；真实合格 CLI 输出缺失；综合验收与正式切换未完成。", "source": REPAIR + "issues/22-live-acceptance-cutover.md"},
]

data = json.loads(OUT.read_text())
data.update({"groups": group_data, "tasks": tasks, "pending": pending, "sources": source_index,
             "head_commit": HEAD, "snapshot_at": SNAPSHOT,
             "milestones": [{"at": commit("aeb6b41")["committed_at"], "label": "22 票发布"}, {"at": commit("bda795f")["committed_at"], "label": "1031 全套通过"}, {"at": commit(HEAD)["committed_at"], "label": "1053 全套通过"}]})
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"output": str(OUT), "groups": len(groups), "tasks": len(tasks), "head": HEAD, "sources": len(source_index)}, ensure_ascii=False))

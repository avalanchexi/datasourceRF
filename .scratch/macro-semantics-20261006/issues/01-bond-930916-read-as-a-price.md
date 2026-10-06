Status: ready-for-agent
Category: bug
Type: task

# 01 — 930916 债券价格指数被当作收益率解读（审计 N05）

## 现象

`CN_BOND_10Y_930916`（中证 10 年期国债指数 930916.CSI，单位 `index_points`，是**价格**指数）在政策传导组（`_POLICY_TRANSMISSION`）里按"收益率"默认规则解读：上涨判为 `tightening`，下跌判为 `easing`。方向正好相反。同组的 `CN_BOND_FULL_PRICE_CNY030` 已列入 `easing_when_up`，930916 被漏掉。

- 位置：`src/pring_cycle/context_projection.py` `_POLICY_TRANSMISSION`（约 52 行）与政策方向函数中的 `easing_when_up` 集合（约 1885 行）；身份见 `catalog.py:234、252`、`tushare_context.py:67`。
- 来源：[审计 N05](../../../docs/research/legacy-pring-model-audit.md)；[需求清单 §3.4 S01](../../../docs/research/pring-indicator-requirements.md)。

## 影响

只影响宏观"政策方向"（`policy_direction`）的传导证据与页面解释；正式阶段不受影响（`domain/stage.py` 丢弃上下文证据）。当前投影的 `transmission_conflict` 可能部分由此造成。

## 修复

- 930916 上涨解读为债券价格走强，在传导组中作 `easing`（与 CNY030 一致）；下跌作 `tightening`。
- 不再依赖"除少数外均为利率"的默认规则：传导组每个成员显式声明"上涨对应宽松还是收紧"，新增成员未声明时报错，而不是默认按收益率处理。
- 文字说明（页面、报告解释）只说"债券价格走强／走弱"，是否政策宽松仍由组内其他证据共同决定（需求清单 S01）。

## 验收

- [ ] 回归：930916 上涨 → 传导证据 `easing`，下跌 → `tightening`；CNY030 行为不变。
- [ ] 回归：传导组新增未声明方向的成员时报错（或测试列出全部成员与其声明）。
- [ ] 受影响测试（上下文投影、宏观状态、Worker 复核上下文）与两例冒烟通过；Codex 两轴审查无阻断。

## Comments

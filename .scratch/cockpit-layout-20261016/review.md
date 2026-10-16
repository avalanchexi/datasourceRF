# 集成分支代码审查（2026-10-16）

基线 conclusion-board 638d125，HEAD c7afb8a；两轴各一次 codex exec -s read-only。

## Standards

(a) 硬违反：[test_conclusion_board_noncanonical.py:125](/home/tywin/worktrees/datasourceRF-cl/tests/web/test_conclusion_board_noncanonical.py:125)通过 `html.Strong` 断言加粗，违反 [spec.md:182](/home/tywin/worktrees/datasourceRF-cl/.scratch/cockpit-layout-20261016/spec.md:182)“不断言样式”；应保留文本断言。

(b) 坏味（判断题，均属 Duplicated Code）：

- [cockpit.py:1500](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:1500)、[cockpit.py:2499](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:2499)重复拼后缀去重，未再次查重。只读复现：输入 `X,X-3,X` 产生两个 `overseas-X-3`，可能打开错误抽屉；应统一分配唯一键。
- [cockpit.py:989](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:989)、[cockpit.py:1833](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:1833)分别渲染同源完整缺口清单，建议两个触发器共用一个抽屉。
- [cockpit_operations.py:102](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit_operations.py:102)、[report.css:222](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/assets/report.css:222)重复维护七项浅色调色值，改色容易漂移，应集中维护。

阻断：有

## Spec

(a) cockpit.py:619、2241：①/⑥未限量，违反“限高滚动或前 N 条”（spec.md:152）。

(b) cockpit.py:480：删②观察接口列表且丢“目录未收录”状态，未保全“同类观察每行全部字段”（spec.md:157）。

(b) cockpit_operations.py:84、120：新增received映射、单个小来源不合并，偏离“未映射值显示原值、灰色”“请求数 <2 的来源合并”（spec.md:176）。

(c) wording.py:243、cockpit.py:87：成员表压过目录、组名回退免标注，偏离“否则查对照表”“未提供中文名”（spec.md:165）。

(c) cockpit.py:1471、1491：核心待处理也标“非典型组合不判定命题与成熟度”，把非典型限定扩大到所有无正式阶段（spec.md:170）。

阻断：有

## 主 agent 处置

| # | 发现 | 处置 |
|---|---|---|
| S1 | 测试以 `html.Strong` 断言加粗 | 修：改为只断言文本；加粗由票 10 截图证明 |
| S2 | ③/② 抽屉键后缀去重不查重（X、X-3、X 撞键） | 修：统一唯一键分配，加反例 |
| S3 | ① 与 ⑦ 两个同源缺口抽屉 | 修：共用一个抽屉，两个触发器 |
| S4 | 桑基浅色调色在 Python 与 CSS 各一份 | 修：颜色只在 CSS 变量维护，Python 只留单一中性兜底 |
| P1 | ①、⑥ 明细未限量 | 不改：① 明细为数行短句；⑥ 已按 120 交易日窗口限量（规格"默认最近 120 个交易日"） |
| P2 | ② 删"观察接口"列表丢"目录未收录"状态 | 修：行抽屉补该状态；保留删除列表（与卡内同类观察重复） |
| P3 | 新增 received 映射；单个小来源不合并 | 接受：避免英文原码；"其他（1）"不如原名，记入票 09 |
| P4 | 组名回退未标注 | 修：回退到组名时抽屉标"未提供成员中文名"；成员项优先于目录名保留（避免融资两行重名） |
| P5 | 核心待处理也写"非典型组合不判定…" | 修：仅非典型写该句；其他无阶段原因写"无正式阶段，不判定命题与成熟度" |
| 遗留 | tests/integration 确认相关旧首页文案断言 4 例失败（自结论板批次起）；家数"978.00 家"；仓单吨数"2175351.0" | 修 |

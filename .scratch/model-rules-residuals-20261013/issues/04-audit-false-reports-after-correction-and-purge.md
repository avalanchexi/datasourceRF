Status: needs-triage
Category: bug
Type: task

# 04：体检在更正版本与已清理数据上的误报

## 现象

1. 对旧运行重跑体检时，截止前已持有、后来被留存清理的声明和投影，在第一层日频记为“未取到”，在派生节计入“待开票”（对照运行：37 格、9 项）。低频节已有“已入库后被清理”分类，日频与派生节没有。第三层（二）把 423 条断链统称“窗口前预热”，其中 3 条在窗口内，措辞不准确。
2. 派生逐日核对用更正版本的投影截止重新选原料（`derived.py:1239`、`:541`、`:201`，计数 `:1187`），票 01 更正版本的信用脉冲 13 天报“重算原料不齐”，生产值没有变化。应改用被更正版本的截止，或按冻结选中编号取值。
3. `derived.py` `_core_only()` 只读 `corrects.scope`；只更正核心的日子以后若被“上一确认阶段更正”覆盖，原范围在 `corrects.carries` 中，会误报“标记不全”。
4. 冻结清单缺 `confirmation_rules` 的旧运行（如 `run-dc0bb2d9…`）报 `KeyError`。

## 来源

[acceptance-20261013.md](../../model-rules-followups-20261012/acceptance-20261013.md) 遗留 5、6；[goal 遗留](../../model-rules-followups-20261012/goal.md)。

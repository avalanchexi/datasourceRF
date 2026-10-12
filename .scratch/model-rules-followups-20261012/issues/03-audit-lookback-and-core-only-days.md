Status: needs-triage
Category: bug
Type: task

# 03：体检未覆盖“回溯得出”与“只更正核心”日

## 现象

(a) 第三层（一）`tools/quality/output_consistency.py:159`、`:168` 要求评估的 `last_confirmed_stage` 与总览相同，未按票 02 的回溯规则核对（本次第二次运行未触发回溯，未复现）；(b) 派生节把只更正核心日的“无派生值”算作缺失，报出“待开票 8 项”（`tools/quality/derived.py`）。体检口径文档与脚本需加入回溯与只更正核心的规则。

## 来源

验收记录遗留 2、9（模型规则补全批次，2026-10-12 收尾汇总）。

## Comments

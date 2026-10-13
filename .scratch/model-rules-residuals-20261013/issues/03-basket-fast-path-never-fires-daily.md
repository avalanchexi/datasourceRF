Status: needs-triage
Category: enhancement
Type: task

# 03：票 06 候选 B 在日常 T+1 运行中不触发快路径，反而多 4 次请求

## 现象

快路径（篮子窗口全持有时 12→4）要求窗口全持有，而日常运行的新目标日在运行前都未持有。`run-0a8dabc2…` 实测 24 次请求（4 次日历预检＋原流程 20 次），只有同一目标日重跑才省。“12→4”至今没有真实样本。另有票 06 遗留：回退时比原流程多 1–4 次日历请求，且回执被链接为篮子输入；回退后原流程仍宽松接受日历；人工入口选日依据只在 CLI 输出，未写入运行记录。两条新分支（请求后行情为空记 `source_empty`；日历回退标注）在真实运行中都没有触发。

## 待分流

保留、撤销，还是改为“先判断目标日是否已持有，再做日历预检”（需用户定，原决定见[票 06](../../model-rules-followups-20261012/issues/06-receipt-and-calendar-residuals.md)）。

## 来源

[acceptance-20261013.md](../../model-rules-followups-20261012/acceptance-20261013.md) 遗留 3、4；[goal 遗留](../../model-rules-followups-20261012/goal.md)“票 06”一条。

Status: done
Category: bug
Type: task

# 06：官方降准回溯找到声明即停，未复核截止时是否可读

## 现象

票 06 把降准回溯的公开上限改为运行截止，但官方回溯找到一条声明就停，没有复核该声明在运行截止时是否可读。10-13 运行的降准事件监测为 `none_stated`，未触发。

## 来源

[验收记录](../../recurring-input-gaps-20261013/acceptance-20261014.md) 遗留 10；[票 06](../../recurring-input-gaps-20261013/issues/06-news-window-and-rrr-lookback-use-run-cutoff.md)。

## 收尾预审关闭（2026-10-20）

已被取代：继任票 11（done，083a7c7）实现截止可读性复核。 依据：`.scratch/wrapup-20261020/phase3-pretriage.md`（Codex 只读预审，主 agent 核对提交与继任票状态）。

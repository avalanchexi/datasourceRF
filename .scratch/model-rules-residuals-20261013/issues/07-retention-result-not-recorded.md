Status: needs-triage
Category: enhancement
Type: task

# 07：留存清理的结果没有写入运行记录

## 现象

Worker 调用留存清理后没有保存 `RetentionResult`（`worker.py:675`，Codex 取证），事后无法还原每次清理删了什么。体检对旧运行重跑时因此只能从原件推断（见本批 04）。

## 来源

[acceptance-20261013.md](../../model-rules-followups-20261012/acceptance-20261013.md) 遗留 7。

Status: ready-for-agent
Category: bug
Type: task

# 11：降准回溯复核截止时可读性

**What to build:** 官方降准回溯只停在运行截止（未给时为目标日结束）时可读的声明上：找到的声明按其公开时间在截止时读不到，就跳过并继续往更早的期刊找；解析失败照旧停止；无声明照旧 `none_stated`。落实[来源票 06](06-rrr-lookback-cutoff-readability.md)；见[规格](../spec.md)“降准回溯”。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `backtrack_rrr_chronicle` 接缝新用例：较新期刊的声明截止时读不到 → 取到更早的可读声明
- [ ] 原有“解析失败即停”“无声明”用例保持通过；受影响测试通过

Status: ready-for-agent
Category: enhancement
Type: task

# 12：体检：SOX 有取数路径后的口径

**What to build:** SOX 有取数路径后，体检把它移出“无取数路径”内置表，按应有格照常核对；接入前的运行仍按授权缺口解释（以生效时刻或目录版本区分，取 09 实际落地的那种）。口径文档“SOX 的授权缺口”“SOX 的永久缺口”两段改写。守体检线规程。落实[来源票 02](02-sox-source.md) 的体检部分。

**Blocked by:** 09

**Status:** ready-for-agent

- [ ] 实跑对账旧运行（如 `run-25ac18e4e3d329e1ea07`）：SOX 仍按授权缺口解释，结论不变
- [ ] 夹具或接入后的运行：SOX 按应有格核对，持有则不计缺失
- [ ] 口径文档同步

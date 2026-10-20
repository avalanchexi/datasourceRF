**结论：Standards 未发现可确认的硬违规；1 项 P3 启发式建议。**

- **可能的 Duplicated Code（静态推断）**：[r4_window_lifecycle.py:674](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/fixtures/r4_window_lifecycle.py:674)、[同文件:747](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/fixtures/r4_window_lifecycle.py:747)及[test_r4_margin_lifecycle.py:71](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/integration/test_r4_margin_lifecycle.py:71)重复组装软件、安装包和两 profile 身份快照。依据 Fowler“重复相同逻辑形状”启发式，建议提取共享采集函数，仍在各子进程内调用，降低新增绑定字段时漏改一处的风险。当前未发现身份检查失效，不作为阻断项。

首尾核验通过：7 文件哈希匹配、零新增提交；四份 baseline 均匹配 r4-before，margin.py 从已审 r3 完整新增 patch 内存还原后亦一致。指定命令顺序输出与封存 diff 逐字节相同，SHA256：
`ef63f47012d3f4689d36426261255807e9e96f2c3378820afd0a89bbee4a2254`。

已核三批最终日志哈希，32 passed／35.76 秒是既有收据；src 未变。r5 修复 OMO 四列 injection 材料合同，未放宽生产守卫；r4 失败属于 prepare 阶段，不能记作融资业务 RED。

重型队列未见终态，不能推断 PUBLIC 成功。Worker [旧 v1 比较路径:485](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/fixtures/r4_window_lifecycle.py:485)仍可能受 legacy margin／CNY 认证门阻断（静态推断），合法 active 尚未证明；依项目测试规则，轻量通过不替代该验收。

本次未委派、改文件、运行测试/构建/校准/回放、联网或读取凭据。
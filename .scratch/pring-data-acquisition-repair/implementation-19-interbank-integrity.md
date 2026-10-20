# 银行间原件、规范化与模型消费一致性

日期：2026-09-09。基点99c495a；承接宏观第42阶段。范围仍是票19/21的真实目标，未关闭来源认证、完整候选、120日或报告/切换门。

## 当前实现

- 从实际 TuShare transmission 共享 DR007 weight 和 Shibor 三期限字段构造；新增公开 `parse_interbank_acquisition` 对照单份请求身份、字段、日期区间及实际响应重建经济字段。
- `interbank_claims_matching_acquisitions` 对 exact claim 的所有原件/规范化制品逐次核验，按同 API 联合批次匹配。保留诊断引用，只让合格原始与派生输入进入模型。
- 已接检索、原报及方向父项、政策利差、PUBLIC 组件回放四入口；新目录生效，内置旧目录分支保留。
- 联合多收据、重复/冲突、元数据和晚修订等边界仍在验证；当前代码不得称为最终验收。

## 实际验证

| 阶段 | 结果与证明范围 |
|---|---|
| [semantic-red43](verification-interbank-semantic-red-43.txt) | 原件加权值1.3859，公开回调错用收盘1.3806，raw/normalized各自hash正确；1失败/2正常通过，实际退出1 |
| [semantic-green43](verification-interbank-semantic-green-43.txt) | 检索修复后3通过，15.81秒，主18923退出0 |
| [context-red44](verification-interbank-context-red-44.txt) | 2失败/1通过；新增采用断言错误地使用当前9月SYSTEM截止，正常8月值也已陈旧。这是测试边界问题，未据此修改生产 |
| [context-red45](verification-interbank-context-red-45.txt) | 固定PUBLIC截止2026-08-29后得到1失败/2正常通过；坏DR仍被模型采用 |
| [context-green45](verification-interbank-context-green-45.txt) | 上下文修复后3通过，9.70秒，主33244退出0 |
| [derived-red46](verification-interbank-derived-red-46.txt) | 新DR raw/normalized损坏2失败，旧OMO及quality场景4通过；真实派生绕过被复现 |
| [derived-green46](verification-interbank-derived-green-46.txt) | 派生父项修复后与检索/采用合并9通过，39.63秒，主2363退出0 |
| [replay-red47](verification-interbank-replay-red-47.txt) | Shibor两项真实漏报invalid；DR两项缺10日预热fixture，不将其计为生产RED |
| [replay-red48](verification-interbank-replay-red-48.txt) | DR补08-18合成输入及08-10真实OMO预热，保留公式依赖后4项均在漏报invalid处失败；前置正常两侧全部通过 |
| [replay-green48](verification-interbank-replay-green-48.txt) | 主会话52202实际退出0，13通过、57.44秒；检索、原报、利差和PUBLIC组件合并范围通过 |
| [conflict-red49](verification-interbank-conflict-red-49.txt) / [green49](verification-interbank-conflict-green-49.txt) | 审查提出同身份异值不应按含value键各计1；公开过滤一条冲突原行后1失败/3通过，修复后4通过、15.28秒 |
| [mixed-red50](verification-interbank-mixed-red-50.txt) | 两种API真实结构但DR normalized混合挂接，公开capture/complete_validation/ingest/selector 1失败/1正常通过 |
| [install50](verification-interbank-install-50.txt) / [mixed-green50](verification-interbank-mixed-green-50.txt) | 安装实际WSL/Service/0x8007274c退出-1，后续未正确阻止测试启动，测试跑旧安装代码为1失败/5通过。此轮不能作为当前修复GREEN；日志完整保留 |
| [install51](verification-interbank-install-51.txt) / [源码核对51](verification-interbank-fingerprint-51.json) | 重装实际退出0，全部工作区/安装Python源相符，再启动mixed-green51；不因旧代码失败回滚修复 |

数值锚点和完整联合关系见[原研究](interbank-normalized-consumption-boundary.md)。CFETS真实原文提供独立字段数值，TuShare transport及PUBLIC时刻明确为合成软件fixture，不是历史TuShare交付认证。回放辅助manifest只在公开组件测试使用，存量模型、认证包和全模型门未被改写。

第55阶段：mixed-green51 实际 6 通过、20.88 秒；joint52 实际 6 通过、30.74 秒。最终 Ruff55/格式55通过，mypy55主会话7889退出0、92文件通过；install55退出0，fingerprint55全部91个应用Python源匹配。[最终双轴复审](verification-interbank-review-55.md)新增发现均0，原非阻断重复解析建议保留。专项范围有重叠，不累加为独立总数。扩大关联回归和默认全套尚待执行，旧宏观378不能覆盖新增银行间代码。

六文件合并回归55已实际启动，原主会话27985；[运行记录](verification-interbank-running-55.json)绑定[162个冻结输入](verification-interbank-inputs-55.json)。当前尚无终态，后续只恢复同一会话；运行中不修改应用/测试。

## 第55阶段终态与后续修订验证

上述会话27985已实际退出0，416通过、0失败、1221.36秒。162输入/4受保护文件不变，91安装源前后一致；[终态记录](verification-interbank-terminal-55.json)保存绑定。此前“正在运行”保留历史，不再恢复该进程。

第56阶段仅扩展同一公开组件回放测试至16个场景：raw/normalized × 损坏/丢失 × DR/Shibor × 原版本/后发版本。72193实际退出1，8通过8失败（97.38秒）：新fixture将 fetched_at 填为较晚的当前时刻，未使用实际收到时间，被已有收据约束拒绝。第57阶段40175退出1，8通过8失败（118.19秒）：修正时间后，后期8月31日回放缺当天数据，被覆盖率前置正确拒绝。两轮均未作为生产RED，生产源码没有因之改动。

第58阶段补齐两侧8月31日的独立真实结构交付；8月28日后发修订作为后期方向比较父项，坏修订不应回退到被替代版本，而8月31日合法最新输入应保留。早期8月28日PUBLIC输出须与修订前完全相同。原版本分支仍检验坏最新成员形成invalid gap；后发父项分支不把可缺方向父项升级为新的全模型硬门。当前主会话85224，日志[revisions58](verification-interbank-revisions-58.txt)，尚待终态。

第58阶段已结束：85224退出0，16通过、110.46秒。第59阶段格式与Ruff通过，mypy59771退出0、92文件通过；91安装源仍匹配。Spec增量复审新增0，Standards增量待回报；应用源码未因56/57两次fixture失败改变。默认全套待启动，不能把上述专项和旧416累加为最终全套结果。

第59阶段Standards已回报：新增硬规范0、实质气味0，原重复解析建议保留；[双轴记录](verification-interbank-review-59.md)完整保留两轴结论。默认全套已实际启动，主会话38573，[运行记录](verification-interbank-full-running-59.json)绑定220输入（52个测试引用原件）及4受保护文件。当前没有全套终态，后续只恢复此会话，不重启、不改运行中的应用/测试/原件；本批未提交，全部真实模型最终门保持开放。

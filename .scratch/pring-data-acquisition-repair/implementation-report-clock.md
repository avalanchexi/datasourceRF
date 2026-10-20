# 报告墙钟回拨与耗时审计修复

2026-09-09；承接已批准修复规格实施32/33、测试1/2/10，以及ADR0006、0009。基点为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`。本切片只修改报告服务及其公开边界测试，不改变数据来源公开时间、系统可用时间或冻结事实骨架。

## 实际故障与诊断

[默认全套59](verification-interbank-full-terminal-59.json)为1146通过、2失败。报告CLI双超时用例在保存尝试时抛出 `report_attempt_time_order_invalid`；另一失败为SQLite连接处的锁错误。[原样复测63](verification-interbank-failures-terminal-63.json)两项通过，没有把原全套改记为通过。

[诊断64](verification-runtime-probes-64.txt)在真实CLI超时路径注入倒退UTC，稳定出现同一异常，采样09:59:59→09:59:58；同时3200次并发原件查询无锁错误。[诊断65](verification-runtime-probes-65.txt)移除CLI进程，只保留公开报告生成及外部超时响应，向前时钟通过、回拨失败；另3600次读写交叠没有复现SQLite锁。两份诊断脚本保存在明确的 `verification-runtime-failures/debug/` 中，不进入默认测试集。

原全套没有保存那两次具体墙钟采样或锁持有者；上述实验确立了报告异常的一种可重复机制，不恢复缺失现场，不认定SQLite错误已解决。最小反例排除了CLI清理作为必要触发条件；相同安装源码和独立数据库也不支持旧安装或跨测试污染解释。

## 实现

ReportService在调用前后独立采样单调时钟；原UTC开始/完成时间按实保存，不抬高、夹齐或回填。ReportRepository只在收到合法非负单调耗时参数时接受完成UTC早于开始UTC，并保存 `timing.basis=monotonic`、实际耗时、报告累计耗时及 `clock_went_backwards` 标记。没有独立计时的旧调用继续拒绝倒序时间。

服务计时覆盖适配器自带的同名 `timing` 元数据；已有输出哈希、部分输出字节、工具事件和错误分类继续保存。尝试读取按记录顺序，报告的get、history、by_client_request统一还原累计单调耗时。没有新计时材料的旧记录沿用原有计算方式，不修改旧存储内容。取消、超时、后备CLI及事实校验规则保持既有行为。

采用单调时间差而非墙钟差，依据[Python 3.12时间说明](https://docs.python.org/3.12/library/time.html#time.monotonic)：系统校时不改变单调时钟，只有两次读数之差有意义。因此不把单调读数充当UTC或任何数据的PUBLIC/SYSTEM时间。

## 验证记录

- [公开反例RED66](verification-report-clock-red-66.txt)：1失败，0.52秒，稳定命中同一异常。
- [GREEN67](verification-report-clock-green-67.txt)：公开回归及原真实CLI回拨脚本2通过，10.68秒。
- [读取一致性RED68](verification-report-clock-query-red-68.txt)：按请求ID读取仍返回零耗时；已接入同一还原路径，最终回归待执行。
- 新增双适配器时钟跳变验证：独立期望2500ms、1500ms及累计4000ms，同时检查幂等请求不重跑适配器；待最终回归。
- 两轴审查：Spec 0、Standards硬问题0，唯一非阻断命名建议已落实为 `_with_runtime_metadata`。Ruff72通过；类型检查与完整报告回归仍在执行流程中。

## 验证环境

早期安装66因虚拟环境没有pip退出1，uv安装67/69成功。格式化69遇到WSL服务超时退出-1，未以此声称格式化或测试完成。之后识别到两个既有项目服务使用同一开发虚拟环境，未停止或重启它们。

后续验证已迁到仓库内 `.tmp/venvs/pring-repair-20260909`，使用Python3.12.12；53项依赖按[原环境版本快照](verification-runtime-dependencies-70.json)固定。离线安装70因缺缓存失败，[固定版本安装71](verification-runtime-install-71.txt)成功安装54包（含本项目）。新的[隔离运行包装](verification-runtime-failures/run-isolated.sh)继续使用仓库持有的ext4测试卷，创建独占测试目录；不再向既有服务使用的开发环境安装本切片后续代码。环境不同是验证执行条件变化，后续需明确核对依赖和安装源指纹。

第74阶段实际终态：完整 `tests/reports` 加原真实CLI回拨脚本共 **38通过、0失败，29.33秒**，主会话45955退出0，见[最终收据](verification-report-clock-terminal-74.json)。225绑定输入及4受保护文件未变，前后91安装源码与53项固定依赖一致。类型检查72发现两处测试时钟返回类型不符合datetime子类协变约定，改为返回Self后，mypy73检查92文件通过；最终Ruff/格式73通过。按请求ID读取及两个新增回归均包含在该实际完整报告范围内，未加总早期重复专项。

当前尚未默认全套复验或提交。SQLite锁故障仍开放；GDP/UST合同、真实来源认证、完整模型、固定120日重放、真实合格AI解释及正式切换均不能由本切片替代。

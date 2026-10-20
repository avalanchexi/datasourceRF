# #25 新交付契约的 Worker 接线（在途验收）

独立整合树HEAD为cc81949，以下源码及测试目前仍是冻结WIP，尚未提交。本记录不是整票关闭或完整Worker通过证明。

## 变化

`refresh_context_sources`读取当前注册目录的显式marker。CN_M1_M2的新契约调用money时关闭旧环比字段，使用四必需成员；CN_SF_TOTAL的新契约调用social_financing_total，保留年度累计流量、月末存量及万元/亿元换算的既定定义。旧目录仍用原六字段money和原三成员SF方法。

无scalars的交付抛出专用`ContextObservationsMissingError(ValueError)`，保留既有错误消息。只有整个family均采用新交付marker时，Worker将其记录为missing_values并继续官方回退；普通schema/身份错误不走此分支。API返回了结构有效的空行时，物理回执可能已是validated；这只说明交付原件结构，不代表该期有模型可用值。来源条件、模型认证和实际采用仍分别判断。

## 已完成证据

- money/SF未接新调用先各自触发真实registered_official_source_identity_mismatch；空行先触发中断刷新缺陷。最初测试准备中的tuple.append异常不算生产RED。
- 9个公开刷新/证据/选值阶段测试通过（typed异常最终改动后23.53秒）：M1四成员、SF累计/存量、两族空行官方回退、旧目录字段、无效月份拒绝、prices/PMI/GDP空行继续。
- Ruff通过；Mypy三个源码通过。两轴复审未留硬问题；异常字符串识别已改为类型。新完整测试的父/子时钟不一致已在启动重型验收前修正并进入材料指纹。
- 当前独立安装包相关回归 **434 passed in321.59s，exit0**，日志sha`d915b3a0f75202376c07dd1632a434db4dcd9d189160f8e56c65bc93542c6d6d`。见`verification-2527-integrated-worker-related-result-20260918.json`。安装与完整测试共用冻结源码；最终前后哈希检查仍等driver终态。

## 仍在运行

driver句柄16639继续执行`test_integrated_worker_delivery.py`，新acquisition-repairs材料通过真实公共准入、接受、120日回放和激活命令准备，外部HTTP及时间为明确合成夹具；ECB仍未认证。完整Worker包括历史09/11、当前软件09/18，官方有/无、逐来源取值/账本/投影/报告以及无效必需M1交付保留旧投影。完成前不得把434项计为完整生命周期通过。

双方缺失P0的阻断反例、隔离变异验证以及真实来源认证/真实候选/实际120日回放仍待独立闭合。MAIN原17项WIP保留，未合并/推送或正式激活/切换。

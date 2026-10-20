# A18 单项恢复与独立验收

日期：2026-09-09。原基点99c495a，唯一执行脚本新增 `verification-catalog/recover_a18_import.py`，9271字节，SHA256 `d996b80778181bcfc36cc92b89adeb1c20e2af1f3105ba6c7415f4c4d850f969`。

## Standards

独立规范审查硬规范0、实质气味0。真实UTC与monotonic仅记录、不调整；新隔离库只新增1张贷款收据；旧OMO只读重建；旧数据和失败状态保留，成功状态仍待独立验证。审查没有执行应用、SQL或测试。

## Spec

独立规格审查0。完整字段比较、排他迁移空schema、领域/模型为0、历史时间与认证不授予，符合规格和A18导入边界。审查没有执行应用、SQL或测试。

## 实际执行

- [恢复执行日志](verification-a18-recovery-04.txt)：实际退出0，只追加1次贷款capture；OMO复核使用旧收据，旧post-check UTC仍标未记录。
- [独立核验日志](verification-a18-recovery-independent-04.txt)：主会话1174实际退出0。标准库只读两库逐行核验，原268条加新1条保留；选用268有效收据覆盖268结果，250原件、268规范化和1858个完整解析值一致。
- [合并核验](evidence-a18-import-recovery-20260909-01/combined-verification.json)：旧失败获取1、旧失败post-check1仍保留；认证、历史PUBLIC/SYSTEM恢复、模型采用均false，来源声明/模型记录0。

这完成A18本次获取准备；1个Q1映射待定、正式来源认证和完整模型最终门保持开放。

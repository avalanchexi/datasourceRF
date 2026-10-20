# A18 本次导入脚本执行前审查

日期：2026-09-09。范围为 `verification-catalog/import_a18_originals.py` 新文件，基点 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`；规格依据 `spec.md` 和 `a18-document-import-readiness.md`。本记录不表示已执行导入或完成来源认证。

## Standards

独立规范审查：硬规范问题 0，实质气味问题 0。排他创建 WSL 隔离目录、仅迁移空 schema、采用真实 capture 时钟、保留失败收据、原件与规范化内容分开保存、Q1 待定映射保持旁路记录，符合本批执行边界。未执行脚本或 SQL。

## Spec

初审发现 1 项 P2：fetch 内立即校验原件 SHA，可能在 capture 保存接收时间及原件之前失败。已将 fetch 改为仅返回完整 bytes，长度/SHA 校验移至 parse，在公开 get 获得 received_at 后执行。窄复审确认问题关闭，剩余 0，范围越界 0。未执行脚本或 SQL。

最终审查脚本 SHA256：`9195385ea3abe6d889353c3db240b0a3153d8fd1d1f33268aac47acf012635a5`。执行前已复算一致；格式与 Ruff 02 通过，90 个工作区/安装 Python 源文件匹配。

根代理另核对研究报告：20,348 字节，SHA256 `3a911f5a1cf84f1b092a1badaae59b10597ff9945ac33b0fef8cff533fff7ff4`，79 个本地引用均存在，17 个读取快照字节及 SHA 全部相符。独立 stdlib 交付核验脚本已准备，实际终态须另见新交付包，不以研究或代码审查替代执行结果。

汇总：Standards 0；Spec 原 1 项已修复并复核，剩余 0。

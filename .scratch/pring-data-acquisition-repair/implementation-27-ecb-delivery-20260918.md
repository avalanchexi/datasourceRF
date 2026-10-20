# ECB 双腿交付与来源复核

检查点：2026-09-18 09:18 Asia/Shanghai。独立工作树
`/mnt/d/cursor/datasourceRF-p2-20260917`，分支 `codex/p2-identity-migration`，提交
`dc44076b6e143ca2c265e1d7740f63de5487d649`，基点为已确认 ECB 身份提交 `06bccc3`。
仅提交本切片 9 个文件，跟踪工作区干净；MAIN 原有 17 项文档/测试 WIP 保留。

## 已实现

- `ecb_reference.py` 为独立 `CN_USDCNY_ECB_REFERENCE_CROSS` 提供本地 ZIP 导入和官方 HTTP
  获取。`ecb-reference-import` / `ecb-reference-refresh` CLI 均要求显式新目录版本。
- 同日 `CNY/EUR ÷ USD/EUR`，单位 `cny_per_usd`，34 位十进制有效数字、ROUND_HALF_EVEN。
  保留数字原文、公式版本、原始 ZIP、CSV 成员哈希及取得/校验回执。fixture 为已下载真实原件，
  SHA256 `56a389450a063c0637462db6e33575b45048e181a8071adc9cef2438c97c9e51`；本轮没有新网络请求。
- 限制 ZIP/解压大小、唯一指定成员、CSV 字段、唯一严格日期和正数。整份响应重新解析，范围外
  错误行也拒收；缺腿保留缺口，不填零。损坏 DEFLATE 的原件及分类不会遗漏。
- HTTP 不跟随重定向，校验来源、状态、MIME、完整性与 Content-Length。读取截断和“ZIP 可解析
  但短于声明长度”均以可追溯的 `source_failed` 结束。不会把本地导入伪装为 HTTP 请求。
- 同两腿重复导入复用首次声明；任一腿改变，即使交叉结果不变，也追加 vintage，旧 SYSTEM 结果
  仍可重现。证明复核缓存最多 4 项，以完整 raw/normalized 字节及上下文为键；每次仍重新读取并
  核对哈希、检查回执身份，修改原件不能复用旧证明。
- 注册来源契约拒绝旧 broker 改名、手填结果、伪造两腿/公式/normalized 和 PUBLIC 时间。
  投影再次核对来源契约；损坏时遵循现有投影方式显示 `source_failed`，原记录值仅供审计。

## 验证

最终 v2 独立安装包 **157 passed in 101.57s，exit=0**。99 项源/安装文件、9 个选定测试文件及
95 项全部测试输入在前后保持一致，提交前再次核对。日志 SHA256：
`735856f0a9a56e736d5d7fb778973a1388ad89d397f501999409af3b48e7d258`。

- `verification-27-ecb-delivery-v2-installed-final-20260918.json` 为终态。
- `verification-27-ecb-delivery-v2-install-20260918.json` 为完整指纹及 wheel 来源。
- Ruff、4 个源文件 Mypy、git diff --check 通过；两轴审查见
  `verification-27-ecb-delivery-review-20260918.md`，最终均无剩余硬问题。
- v1 安装包的 156 项通过仅验证 Content-Length 修正之前的代码，不替代 v2。
- 公开 RED 包括新导入入口、重复修订、缺腿审计、HTTP/CLI、投影原件损坏、坏 DEFLATE、
  IncompleteRead、Content-Length 短体。早期测试夹具/API 属性错误已修正，最终以安装包为准。

用 v2 安装包在独立合成未认证目录导入同一真实原件的 2026-03-09 至 09-17 窗口：
**136 个 SYSTEM 参考日值，PUBLIC 为 0，导入约 0.791 秒**。见
`verification-27-ecb-window-batch-20260918.json`。136 个 ECB 参考日不同于 120 个中国交易日，
此例不是实际来源认证或真实模型回放。

## 后续门与已知边界

此切片不等于 #27 完成。当前完整 Worker 尚未调用新适配器；ModelInputSelector 尚未加入 ECB
来源复核 family；TargetBoundEvidenceRepository 仍为所有模式附加严格 PUBLIC 目标日过滤，
因此仓库中的 SYSTEM-only 值尚不能在有目标交易日的完整流程中按用户决定使用。

下一步先建立公开反例：已认证合成 ECB 值在实际取得前不可用，在当前 SYSTEM 可用；PUBLIC
和取得前历史目标日保持缺口；损坏原件不可采用。沿用模型版本冻结要求明确目标日规则边界，
不能直接全局去掉 PUBLIC 过滤而改变旧模型或让后来修订泄入过去。随后连入 Worker 与物理请求账本。

真实来源认证材料、真实候选、120 中国交易日回放及显式激活/系统切换仍须完成；旧 FXCM/TMA
历史与 TMA 无授权缺口保持，其他 VIX/SOX/CFETS 项继续处理。#25 Worker 的 M1 四字段参数及
SF 总量方法也仍待接线；GDP 8 个必需成员不能缩减。Task D 已完成 1684 项，不要重启。

## 资源

本轮两次 NTFS 透明压缩均未删除、移动或改写内容：1654 个 archived_sessions 文件哈希不变，
compact 汇总节省 454,919,819 字节；1913 个 2026-09-16 UTC 前未修改的 sessions JSONL 文件
哈希不变，节省 1,123,051,427 字节，39 批无失败。记录在 `resource-*-sessions-*-20260918.*`。
最新 C 盘约 8.7 GiB 可用，原生根盘约 832 GiB 可用。主机还有其他空间变化，净可用空间变化
不能全部归因于压缩。活动会话、SQLite、证据、测试缓存及 WSL 均保留。

本轮所有执行句柄已终态，无活动测试/构建/压缩。未合并、推送、认证、激活或切换，目标保持 active。

# ECB 人民币参考交叉汇率

`CN_USDCNY_ECB_REFERENCE_CROSS` 是独立 P2 背景指标，计算同日 ECB 的
`CNY/EUR ÷ USD/EUR`，单位为人民币/美元（`cny_per_usd`）。使用 34 位十进制有效数字和
`ROUND_HALF_EVEN`。它不同于 CNH 即期或中国 16:30 收盘价；旧 FXCM/TMA 历史继续使用原身份。

来源为 [ECB 欧元参考汇率](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)。
交叉汇率是项目计算值，并非 ECB 直接发布的报价。原始 ZIP、CSV 哈希、同日两条原值、公式和
采集回执均保留。缺腿不填值；相同两腿重复采集保留首次 SYSTEM 可用时刻，原值修订追加版本。

先初始化位于原生 Linux 文件系统的运行目录，并通过既有候选准入流程注册含上述独立身份的
新目录。把 `ECB_CATALOG_VERSION` 设置为该实际目录版本；采集命令不会创建或认证目录。

已有原件可以本地导入，`--url` 须填写它实际来自的 ECB 历史资源地址：

```bash
pring-cycle ecb-reference-import \
  --runtime-root /path/to/runtime \
  --input /path/to/eurofxref-hist.zip \
  --url https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip \
  --start 2026-03-09 --end 2026-09-17 \
  --definition-version "$ECB_CATALOG_VERSION" --json
```

通过官方资源刷新使用：

```bash
pring-cycle ecb-reference-refresh \
  --runtime-root /path/to/runtime \
  --start 2026-03-09 --end 2026-09-17 \
  --definition-version "$ECB_CATALOG_VERSION" --json
```

本地导入记录为 `document_import`，网络刷新记录为 `official_http_get`；失败保留可取得的原件
及获取尝试。每次刷新下载完整 ZIP，只为指定范围内的有效日期写入声明，不承诺每个中国交易日
都有 ECB 参考值。

完整历史文件的 `Date` 和通常发布日程不能证明逐日实际发布时间。因此本接口的
`release_at`、`public_available_at` 保持为空，SYSTEM 从实际读取并校验后可见；不会补造历史 PUBLIC。
目录原有认证状态保持，投影复核失败时显示 `source_failed`，留存数值仅供审计。

当前命令已可独立采集；完整 Worker 调用、目标交易日下 SYSTEM-only 证据的采用边界、真实来源
认证和版本回放仍待交付。采集成功不等于认证、正式激活或系统切换。

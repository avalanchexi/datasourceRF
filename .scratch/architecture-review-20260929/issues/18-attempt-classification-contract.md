# 18: 获取尝试的分类契约

**What to build:** 由执行每一步的适配器当场记录各步结果（源失败、结构拒收、入库拒收、本地处理失败）、三类原始原因（外部码、本地规则原因码、异常类）与交付完整性（完整、部分缺成员、无需新增、来源空交付）；字段词汇由获取结果模块定义。外层不再按 Python 异常类型重新定性。

**Blocked by:** 17（改同一批写入点，串行做）

**勿并行：** 02、04、05、09、10、15、19、20、23、24、25、27、28、30（同改：Worker 编排与取数；缺口清单与时效；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 4 失败分类归属（用户决定，2026-09-29）；逐来源事实见 [codex-survey-c4b.md](../codex-survey-c4b.md) 第 3–8 条。 规格：[spec.md](../spec.md)「五、获取结果模块」。

## 现状（不一致处）

- `TypeError`：Worker 的 TuShare／EIA 路径记 `adapter_failed`（`worker.py:1591`、`:1952`），官方宏观、国债、EIA HTML、ECB 记 `validation_failed`（`official_context.py:867`、`ecb_reference.py:508`）。
- HTTP 非 200：官方宏观／LPR／EIA API 抛 `ValueError`→`validation_failed`（`official_context.py:2560`、`official_lpr.py:404`、`eia_context.py:216`），国债／EIA HTML／ECB 抛 `OSError`→`source_failed`（`treasury_context.py:366`）；前者不保留 HTTP 数字。
- HTTP 错误正文：回执先记 `received` 再失败，落成 `structure_check=rejected`（`acquisition.py:212`、`:285`），进缺口清单成为"结构拒收"。
- 缺标量：增量／reviewed 家族记 `missing_values`，其他上下文家族记 `validation_failed`（`worker.py:1943`）；`missing_values` 既表示"已全部持有、无需新增"，也表示"来源空交付"。`verified_candidate` 可伴随缺格（`treasury_context.py:432`、`eia_html.py:461`、`ecb_reference.py:615`）。
- 入库结果：国债 CSV、EIA、ECB 不回写 `ingest_result`（`treasury_context.py:413`）；官方宏观有回执入库结果但无指标 `stage`。
- LPR 失败尝试只记期次与提供方，无类名、原因、阶段（`official_lpr.py:430`）。

## 已定决定

- 请求是否发出／收到／本地导入由执行请求的适配器与回执仓库记录；调度上不发（缺凭据、预算、未发布）由 Worker 或检索账本记录。
- 不设全局"异常类型→分类"对照表；适配器在步骤边界翻译，Worker 的异常翻译只作兜底并记为本地处理失败。
- VIX、CFETS 报价文件解析错记源失败，属适配器按规格判定（`.scratch/gap-sources-20260925/issues/06-vix-cboe-official.md:8`），维持。
- 郑商所"答复了但缺文件"与"没连上"的区分（ADR-0032）保留在原因里，调度仍可读取。
- 部分交付不算失败；缺口清单等消费者按新字段映射各自类别，旧 outcome 只作兼容输入。

## 验收

- [ ] 各来源适配器按模块定义的字段记录步骤结果、原因与交付完整性；上表各不一致处统一。
- [ ] HTTP 错误响应记为源失败（带 HTTP 码），不再落成结构拒收。
- [ ] 国债 CSV、EIA、ECB 回写入库结果；LPR 失败带原因。
- [ ] 按 TDD 在各来源接口上各补一例：源失败带外部码、结构拒收带规则原因码、入库拒收带契约原因、部分交付列出缺失成员、无需新增与来源空交付区分。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过；涉及 Worker 取数，另加跑完整目录正例，记录退出码与耗时。
- [ ] 代码审查无阻断。

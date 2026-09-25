Status: done
Type: task

# 03 — 两融最新一日部分交易所已发布时等待而非拒收

**问题：** 本轮 `margin` 结构拒收（`tushare_margin_exchange_coverage_incomplete`），上轮未出现。

**复现：** 同参数（20260216–20260924）两次取数原件比对：9/25 01:24 那次 9/24 三所均无行 → 通过（到 9/23）；9/25 14:01 那次 9/24 仅 SSE 一行（中秋休市，SZSE/BSE 未发布）→ 沪深口径 `_sse_szse_margin_scalars` 整批拒收。另发现三所口径 `margin_financing` 不校验覆盖，会把 9/24 只含 SSE 的行求和为 13318 亿（前一日完整值 26253 亿），静默产出错值；其登记复核 `parse_margin_acquisition` 也会整批拒收。

**修复：** `_published_margin_days`：每行先完整校验（交易所合法、不重复、数值有效），再判覆盖——只有**请求终点日**（`end_date`）缺所需交易所时视为尚未发布、整日不出值（与整日缺行同等对待）；终点日之前任何一天缺所仍 `tushare_margin_exchange_coverage_incomplete`。应用于沪深口径（`_sse_szse_margin_scalars`，含登记复核）、三所口径 `margin_financing`（原先不查覆盖、不查重复，现与另两处一致）及三所登记复核 `parse_margin_acquisition`（经 `margin_financing_candidate(publishing_day=)`，仍把原始响应交给 `_call`，保留 `code` 校验）。

下游：剔除不重置应有期。两融推定下一交易日 09:05 发布、宽限一个交易日；宽限内为 `awaiting_release` 不列缺口，超宽限落后一期沿用并列 `freshness_gap`（Codex 读码，`freshness.py:99/254/334`）。

- [x] 用 9/25 真实原件回放：两口径均到 9/23、294 值，不再拒收
- [x] 新增例：沪深/三所终点日部分发布、登记复核、终点日前缺所仍拒（两口径）、终点日未知交易所/重复行仍拒、部分日不是请求终点日仍拒、复核回执非零 code 仍拒
- [x] `test_registered_margin_rejects_invalid_delivery_with_failed_receipt[missing_exchange]` 的缺所挪到终点日之前（单日缺所按新规则属“未发布完”）

## Comments

- 2026-09-25 Codex 只读复核（已逐条核实）：初版先剔除后校验，会让终点日的重复/空值/负值随整日删除而漏检；等待不以请求终点为界；三所口径不查更早日覆盖；复核重包装响应丢了 `code` 校验。均已按上文修复。
- 2026-09-25 验证（01–03 合并一轮，dev-venv 重装后）：受影响 28 个文件 `check.py quick` 569 例过，用时 2137.8 秒（超 180 秒目标：文件多且含检索集成用例，照实记录）；切片冒烟 2 例过，86 秒；完整目录正例 `test_worker_registered_catalog.py` 1 例过，133 秒；三核心反例 `test_core_carry_forward.py` 3 例过，185 秒。C 盘始终 67G 余量。

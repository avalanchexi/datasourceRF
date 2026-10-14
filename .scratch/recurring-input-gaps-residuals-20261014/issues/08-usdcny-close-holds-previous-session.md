Status: done
Category: bug
Type: task

# 08：16:30 收盘价持有上一交易日

**What to build:** 09:30 的计划运行持有上一交易日的人民币 16:30 收盘价（`CN_USDCNY_CLOSE_1630`）。先只读调查中国外汇交易中心有无可按日期查询历史 16:30 收盘价的官方接口（外部访问串行）：有则作为 P2 行情来源替换盘中图表文件，并补齐窗口内缺日；无则 Worker 在当天 16:30 后、P0 截止前单独取一次当天收盘价（单来源取数，不是完整运行）。两种做法都只认 16:30 收盘点、不取 03:00 夜盘收盘。落实[来源票 01](01-usdcny-close-previous-day.md)；口径见[规格](../spec.md)“16:30 收盘价”各条。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 调查结论（接口、是否按日期可查、样本应答）写入本票 Comments，选定做法
- [x] `refresh_quote_source` 接缝上的测试：09:30 之后的运行持有上一交易日收盘价
- [x] 只有当前交易时段时记“来源为空”，不报错；夜盘收盘不被取；解析失败记来源失败与原因码
- [ ] （历史接口做法）窗口内缺的上一交易日能补回——不适用：中国货币网无历史接口，采用退路，见 Comments
- [x] 时效规则不变（滞后一个交易日即现行）；受影响测试通过

## Comments

### 2026-10-14 调查（中国外汇交易中心按日期查询的历史 16:30 收盘价）

结论：**中国货币网没有公开的、可按日期查询历史 16:30 收盘价的接口**，首选做法不成立，选定**退路**（Worker 当天收盘后单独取一次）。

外部请求均在 `flock /tmp/pring-external.lock` 下逐个发出，取到即停（共 10 次，全部 200，除英文 `/english/mkdatapfx/` 为 404）：

| 请求 | 所见 |
|---|---|
| `/chinese/mkdatapfx/`（外汇市场行情） | 片段仅 `cpair-quot-cn`、`dollar-ask-day-chart`、`fcl-we-av-rate-inner-cn`、`rfx-sp-quot-cn`、`rfx-sw-quot-cn`，都是当前行情 |
| `html/fx/dollar-ask-day-chart.html`（日内走势图片段） | 只请求 `fx/rfx-sp-iday-chrt.json`，无日期参数、无历史链接 |
| `html/fx/rfx-sp-quot-cn.html`（即期报价片段） | 当前买卖报价（`fx/rfx-sp-quot.json`）；外链只有“中间价”和“人民币外汇即期月报” |
| `/chinese/bkccpr/` 侧栏（基准） | 外汇类只有中间价、参考汇率、汇率指数、USDCIROR 与各曲线，无“收盘价” |
| `/chinese/mtdexdaily/`（每日速递） | 只有拆借、回购、现券、债券远期、利率互换、债券借贷，无外汇 |
| `/chinese/mtmoncjgl/`（统计月报） | 有“人民币外汇即期月报”，为月度统计，不是逐日 16:30 收盘价 |
| `/english/`、`/english/mdtrptdbl/`（英文 Daily Bulletin） | 只有本币产品，无外汇收盘价 |
| `assets/js/cm-basic.js` | 只出现 `ags/ms/`、`dqs/rest/` 等通用前缀，无外汇收盘价历史接口名 |

另据 2026-09-25 的调查（gap-sources 票 07）：参考汇率历史 `/ags/ms/cm-u-bk-fx/RefRateHis` 只有整点参考汇率（16 时），不是 16:30 收盘价；SDDS 汇率的“即期”是中间价。两者都不可替代。

**选定做法（规格“退路”）**：保留盘中图表文件 `rfx-sp-iday-chrt.json` 与现行解析规则（只认 16:30 收盘点，不取 03:00 夜盘，`closeSpotPrice` 须与快照 16:30 点一致）。Worker 在计划开启时，于已存上交所日历写明开市的日子，从时效登记的更新时刻 16:35 起至 P0 截止 21:00（含）止，用现有 `refresh_quote_source` 单独取一次当天收盘价：只取这一个来源，不建运行、不生成评估或报告。取到当天值即当天不再取；文件尚无收盘价（来源为空）或取数失败时，10 分钟后再试，到截止为止（同日历暂缓的重试间隔）。次晨 09:30 的计划运行照常取文件（当前时段无收盘价，记“来源为空”），持有上一交易日由前一晚的取数提供。

理由：首选不成立；退路是规格明列的做法，单来源取数不新增完整运行（ADR-0041 否决“当晚和次晨各跑一次”的理由不涉及）。只在计划开启时取，因为它服务于次晨的计划运行，且 ADR-0010 计划关闭时 Worker 不主动发外部请求。已知局限：当晚 16:35–21:00 机器休眠或 Worker 未运行，那一天的收盘价就取不到，也无法补回（来源不能按日期取）；03:00–09:30 之间文件仍含前一时段收盘价，若日后要加次晨补取需另行决定（规格只写了“16:30 之后、当天 P0 截止前”）。

### 2026-10-14 进展

- 阶段一（`refresh_quote_source` 接缝）：新增 `tests/integration/test_usdcny_close_refresh.py` 前 4 例——前一晚取到的收盘价在次晨只有当前时段的文件下仍被持有（次晨记 `source_empty`）；只有当前时段记“来源为空”不报错；03:00 夜盘收盘与结构不符的文件记 `source_failed` 并附原因码。现行解析器已具备这些行为，4 例首跑即绿（特征测试，钉住退路所依赖的行为）。
- 阶段二（Worker 晚间取数）：先写 7 例（红：`CloseCheck`／`fetch_close_if_due` 不存在），再在 `worker.py` 实现并接入 Worker 循环，转绿。接缝与 `submit_schedule_if_due` 同形：计划开启、已存上交所日历写明开市、生效目录登记该指标时，16:35（时效登记的更新时刻）至 P0 截止 21:00（含）首次检查取一次；当天值入库即当天不再取；来源为空或失败 10 分钟后再试；计划关闭、休市、日历未写明、内置目录均不取。

### 2026-10-14 实施收尾

- 改动：`src/pring_cycle/worker.py` 新增 `CloseCheck`、`fetch_close_if_due`、`_close_catalog_version`，接入 `run_worker` 循环（调度检查之后重新读时钟再判断）；`refresh_quote_source`、解析器与时效登记（`chinamoney:usdcny_1630`，16:35，滞后 1 个交易日）均未改。`docs/development/local-runtime.md` “P2 行情官方文件”一段补写晚间取数与已知局限。新增 `tests/integration/test_usdcny_close_refresh.py` 13 例。
- 测试：`tools/check.py quick` 本票文件＋`tests/adapters/test_quote_sources.py`＋`tests/integration/test_worker_execution.py`＋冒烟 `test_manual_run_cannot_backdate_daily_core_availability`：68 通过，72 秒；另一冒烟 `test_worker_completes_a_valid_noncanonical_projection_and_report` 与 `test_gap_source_repairs.py`、`test_retrieval_p2_lenient.py`：17 通过，126 秒；重型 `test_worker_registered_catalog.py`＋`test_core_carry_forward.py`（`flock /tmp/pring-heavy.lock`）：4 通过，294 秒（在 e274ca1 上跑；之后只改了新函数内部与循环一行，重型用例不经 Worker 循环，未重跑）。`ruff check`、`ruff format --check` 通过；`mypy` 对改动文件无新错误（仅 `tests/conftest.py:21` 既有一条）。
- 审查（Codex 两轴）：首轮规格轴阻断 2 条、标准轴阻断 4 条（重合 2 条），全部采纳——请求前先查当天是否已持有（防重启重复取、防重启后失败覆盖成功记录）；循环在调度检查后重新读时钟；模型清单解析、刷新与持有检查全部纳入异常隔离，记 `close_fetch_failed` 事件并 10 分钟后重试；“次晨持有”测试改用 `install_runtime_clock` 跨日并按次晨截止读取。定向复审：阻断无。
- 遗留：当晚 16:35–21:00 Worker 未运行或机器休眠，当天收盘价无法补回（来源不能按日期取）；如需次晨 03:00–09:30 补取（文件此时仍含前一时段收盘价），需用户另行决定。真实效果待票 13 收尾验收（需当晚 Worker 在线）。

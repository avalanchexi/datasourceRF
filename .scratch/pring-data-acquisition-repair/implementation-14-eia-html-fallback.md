# 票14：无密钥时改走官方历史页面（2026-09-16）

依据 [连通性实测](verification-connectivity-20260916.md)：EIA 官方 API 密钥实测 403 不可用；无需密钥的官方历史页面 `RBRTED.htm`/`RWTCD.htm` 实测 200。用户答复"EIA key 可能没有，是否可以更换数据源"——结论是不必换源，项目本就有第二条入口。

## 行为

`worker.py` 的 EIA 分支抽成公开的 `refresh_eia_context`，选择顺序与留证规则：

1. 有密钥 → 走 API（原行为）。成功即记 `eia_official_candidate` / `verified_candidate` 并返回，不再请求页面。
2. 无密钥 → 记 `eia_official_candidate` / `missing_credentials`（`request_sent=false`），再走页面。
3. 有密钥但被拒或出错 → **先按原分类记该渠道的失败**（`source_failed`/`adapter_failed`/`validation_failed` 与 `error_type`），再走页面。失败不被回退掩盖。
4. 页面渠道记 `eia_html_candidate`，附 `publication_precision=release_date_only`——官方历史页只给到发布日期，发布时间精度低于 API，如实标注。页面本身失败也按原分类记录。

两行仍是仅背景用途、`awaiting_source_certification`，不因取到真实值而升级。`eia_html.py` 的 `_fetch_history` 改为公开的 `fetch_eia_history`，便于 Worker 注入与测试替换。

## TDD 与验证

- RED：新测试 `tests/integration/test_worker_eia_html_fallback.py` 因 `refresh_eia_context` 不存在而失败。
- GREEN：2 通过——无密钥回退取到 2026-09-01 Brent 96.02、两份 `eia_history_html` 收据、声明仍为等待来源认证；密钥被拒时先记 `source_failed`（`OSError`）再回退。
- 相关回归：`test_eia_html_acquisition.py`、`test_worker_eia_html_fallback.py`、`tests/adapters/test_eia_context.py`、`test_context_acquisition_receipts.py` 共 69 通过/122.1秒。
- 注册目录用例同步更新：四场景中"无可用密钥"的三种现在断言走页面渠道并取到真实值，`success` 仍走 API 且不请求页面；另外三处会触网的完整运行改为读归档原件，测试不出网。
- 注册目录 8 用例（含一次材料重建，新身份 `e516aad7…`）：首轮 6 通过后被守护误杀（见下），补跑余下 2 个场景 2 通过/488.6秒。**8 项在同一版本上全部通过。**
- ruff、`mypy src`（96 源文件）通过。

## 一次误杀与守护修正

首轮跑到第 7 个用例时，C 盘可用空间在一个 15 秒采样点内从 6GB 掉到 1GB，守护按"单点低于阈值即终止"把运行杀掉。事后核查：WSL 虚拟磁盘未增长（287.6GB 不变），swap 仅增 1.3GB，282 个采样点中 281 个为 6GB，随后自行恢复到 5.6GB——是 Windows 侧的瞬时占用，不是本次运行造成的。守护改为**连续两次低于阈值才终止**，避免长任务被一次波动误杀。中断日志保留为 `verification-eia-fallback-20260916-interrupted.txt`，不计为失败。

## 边界

- 页面入口只解决"取到真实值"，不构成来源认证；EIA 两行的认证状态不变。
- 其余 P2 渠道（CME/LBMA/CBOE/纳斯达克等）未获许可，保持缺口。

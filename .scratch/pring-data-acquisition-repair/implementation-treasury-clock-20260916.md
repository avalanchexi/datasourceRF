# 美债上下文用例的时钟定时炸弹（2026-09-16）

## 现象与根因

票17联合验证期间，模型目录回归出现 6 个既有失败，全部是 `tests/models/test_candidate_admission.py` 的美债用例：`test_registered_treasury_original_supports_system_context_without_inventing_public_time`（5个参数）与 `test_registered_treasury_context_rechecks_hash_consistent_receipts[none]`，断言 `claim_ids <= set(adopted)` 失败且采用集合为空。以 HEAD 源码与 HEAD 测试的导出副本单独运行同样失败，确认与票17、#16 的改动无关。

只读排查结论（不是产品缺陷）：

- 采用过滤在 `src/pring_cycle/context_projection.py:521-537`：只有 `status` 为 `current`/`available` 且有值的行，其声明与派生父项才进入 `model_input_observation_version_ids`。
- 状态由 `_period_freshness`（`context_projection.py:1701-1705`）按 `as_of.date() - period_end` 与 `evidence_max_age_days` 比较得出；美债两项走日度，上限 **10 天**（`src/pring_cycle/metric_contracts.py:20-26`）。派生的 `UST_2S10S_SPREAD` 继承父项过期状态，值仍算得出（41.0），但不被采用。
- 两个用例把原件期次钉在 **2026-09-04**，却把 `as_of` 传成 `datetime.now(UTC)`。它们随 `c566702`（2026-09-14）提交，正是该期次仍在 10 天窗口内的最后一天；2026-09-15 起必然失败。

## 修复

不改产品规则，不改原件期次；按仓库既有写法（`tests/integration/test_derived_context_freshness.py:67-92` 对同样两个指标用固定 `as_of`）把时间钉住：

- `tests/conftest.py`：把 `runtime_clock` 的安装逻辑抽成 `install_runtime_clock(monkeypatch, request, origin)`，夹具本身仍以真实当前时刻为起点，语义不变；需要固定时间线的用例显式传入起点。
- `tests/models/test_candidate_admission.py`：两个美债用例改为在 `TREASURY_FRESH_CLOCK = 2026-09-05T12:00Z` 上运行（`TREASURY_FIXTURE_DAY` 的次日）。收据时间、声明可见时间与 `as_of` 都落在同一条固定时间线上，因此与运行当天无关。
- 同时把"超窗即不采用"变成显式被测行为：在同一用例中再以 `TREASURY_FIXTURE_DAY + 11 天` 为 `as_of` 构建一次上下文，断言价差值仍为 41.0、两项美债行状态为 `stale`、声明不在采用集合中。原先这条规则只是碰巧由当天日期触发。

## 验证

- `tests/models/test_candidate_admission.py -k treasury`：16 通过/43.7秒（此前 6 失败）。
- 时钟夹具改动的影响面：`tests/integration/test_context_acquisition_receipts.py`、`test_derived_context_freshness.py` 共 45 通过/74.2秒。
- ruff check/format 通过；`mypy --follow-imports=silent tests/models/test_candidate_admission.py` 无错。`tests/conftest.py:16` 的 `no-untyped-def` 为既有项，且 conftest 不在项目 mypy 门槛（`packages=["pring_cycle"]`）内。
- 注意：`test_candidate_admission.py` 与 `conftest.py` 都是隔离材料的构建器，本次改动使材料 `8a84b451…` 失效，下次重型验证时随其他改动一并重建。

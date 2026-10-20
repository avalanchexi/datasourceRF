# OMO 新目录测试：合成 PUBLIC 日历父项

2026-09-09，只读源码快照；没有运行应用、测试、SQL 或网络，也未重读前份报告的七个宏观原件。**现有公开接口允许构造所需 fixture，无需修改模型门或给 `refresh_core_history` 增加发布时间参数。**已有直接先例是 [`test_registered_core_public_replay_rechecks_selected_originals`](../../tests/models/test_candidate_admission.py#L5424)：L5471 公开 acquire，L5519 构造明确合成 PUBLIC 声明，L5542 公开 append。

## 最小构造

先沿同文件 `prepared_request`、`submit/save` 在独立 `tmp_path` 创建合成审查的新登记目录，取得 `model_id`、`manifest`、`version`。模型必须仍包含已声明的 `CN_EQUITY_CORE_000985` 契约及 `repo-net-injection-trading-calendar-v0002`；不是降低认证状态或改 source codes。以下为未执行的测试代码骨架，假定已有该隔离 `paths` 和 `version`：

```python
from datetime import UTC, date, datetime
from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import (
    AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput,
)
from pring_cycle.source_adapters import TushareCoreAdapter

metric = "CN_EQUITY_CORE_000985"
day = date(2026, 8, 28)
raw = (
    b'{"code":0,"data":{"fields":'
    b'["ts_code","trade_date","close","pre_close","pct_chg"],'
    b'"items":[["000985.CSI","20260828",101,100,1]]}}'
)

def transport(payload):
    assert payload["api_name"] == "index_daily"
    assert payload["params"] == {
        "ts_code": "000985.CSI",
        "start_date": "20260828", "end_date": "20260828",
    }
    assert payload["fields"] == "ts_code,trade_date,close,pre_close,pct_chg"
    return raw

acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
acquired = TushareCoreAdapter(
    "synthetic-token", transport=transport,
).acquire_core_bars(
    acquisitions, metric, start=day, end=day,
    expected_business_dates=(day,),
)
receipt = acquired.receipt
assert receipt.received_at is not None and receipt.validated_at is not None
assert receipt.raw_hash is not None and receipt.normalized_hash is not None

# Explicitly invented test publication, not a TuShare source timestamp.
published = datetime(2026, 8, 28, 8, tzinfo=UTC)
event_id = "synthetic:core-public:CN_EQUITY_CORE_000985:2026-08-28"
evidence = EvidenceRepository(paths.database)
stored = evidence.append_source_claim(SourceClaimInput(
    metric_id=metric, definition_version=version,
    period_kind="business_day", period_start=day.isoformat(), period_end=day.isoformat(),
    dimensions={}, value=101, value_state=EvidenceValueState.REPORTED_VALUE,
    unit="index_points", provider="tushare",
    source_reference="tushare:index_daily:000985.CSI:2026-08-28",
    release_event_id=event_id, release_at=published, public_available_at=published,
    fetched_at=receipt.received_at, available_at=datetime.now(UTC),
    certification_status="certified", quality_status="validated",
    acquisition_id=receipt.acquisition_id,
))
```

公开 [`acquire_core_bars`](../../src/pring_cycle/source_adapters.py#L176)用真实 capture 机制生成 validated 回执和 raw/normalized；注入的是外部 transport，不是内部校验函数。`expected_business_dates=(day,)` 是明确的隔离测试日历断言；这一个数据行不证明真实交易日历全集。最小 OMO 到期函数只需目标 08-28 这个合格日就能将 08-21 的操作映射到 08-28；可以补其他日增加覆盖，但不必为此构造三核心完整 120 日回放。

[`append_source_claim(s)`](../../src/pring_cycle/evidence.py#L424)仍执行新目录字段/状态守卫与原件检查。必须保持 fetched_at 等于关联回执 received_at，available_at 不早于 validated_at；不能伪造一个无 acquisition 的 certified 日历行。当前 [`_validate_core_originals`](../../src/pring_cycle/evidence.py#L254)会核两类制品、回执身份和原行日期/收盘值。`parse_core_acquisition` 重建的是 MarketBar 数组，不包含 SourceClaim 的合成 PUBLIC 字段，因此该公开入口允许显式测试声明时间；**这种允许不构成真实 TuShare 历史 PUBLIC 证据**。

## 公开读取与 OMO 断言

1. 用 `acquisitions.read_content(receipt.acquisition_id, "raw")` 断言等于上述 raw；读取 normalized 为非空 JSON 数组。通过 `evidence.source_claim_acquisitions_many((stored.claim_id,))` 验证准确 claim→回执→两类制品关联。不要手写另一份 normalized 代替 adapter 输出。
2. `evidence.metric_series(metric, mode=PUBLIC, as_of=published−1微秒, definition_version=version)` 无结果；在 `as_of=published` 得到唯一 selected value 101、指定 claim ID；SYSTEM 在 append 后当前时刻也可见。此为接口断言设计，本报告未执行。
3. 公开提交 `RunRepository.submit(command_type="targeted_refresh", target_business_date="2026-08-28", client_request_id=唯一fixture标识, model_version_id=model_id, system_as_of=append后当前时刻, release_event_id=event_id, metric_ids=(metric,), period="2026-08-28")`，分别调用 [`select_retrieval_input(paths, run, mode=PUBLIC/SYSTEM)`](../../src/pring_cycle/search_evidence.py#L46)，应 complete 且仅选择此 claim。这一 selector 实际调用 [CoreInputValidator](../../src/pring_cycle/search_evidence.py#L100)，核 raw 重解析及 normalized 对应；单纯 `metric_series` 有值不等于通过它。
4. 再导入前份文档的 08-21/28 真实 OMO 原件，以已登记 manifest 调 `build_context_projection(..., as_of=append后当前时刻, target_business_date="2026-08-28", as_of_mode=SYSTEM, persist_derived=True)`。期望 `maturity_basis="derived_7d_trading_calendar"`、净额 −750、maturity_amount=950；派生 `input_observation_version_ids` 包含两条 OMO injection 及此日历 claim，`trading_calendar_observation_version_ids` 仅该日历 claim，公开 `derived_trace` 同样绑定。若采用 PUBLIC，令 as_of 为 08-28 中国日末；synthetic PUBLIC 的 16:00 中国时间在上界内，不需要修改目标上界。

静态限制：当前 [`_certified_trading_day_points`](../../src/pring_cycle/context_projection.py#L1027)仅通过 `_certified_point` 过滤 series，没有在此调用 CoreInputValidator。因此以上步骤 3 是日历 fixture 的独立公开资格验证，**不能代称 OMO 上下文本身已在消费时再次核 core 原件**。如果本轮要验“日历制品随后损坏仍被拒绝”，需单独建立实际反例；本报告不宣布该风险已复现或要求顺带改变实现。

## 默认未知 PUBLIC 的替代 SYSTEM 路径

[`refresh_core_history`](../../src/pring_cycle/core_history.py#L131)明确调用 `publication_times(None, ...)`；其 raw 响应无可靠公开字段，输出 PUBLIC 仍未知。它没有已知 PUBLIC 参数，不能把取得时钟或收盘点填进去。

- 无 synthetic PUBLIC 时，普通 `EvidenceRepository.metric_series(..., mode=SYSTEM, as_of=取得后)` 可以验证 core 已取得值；[full-run SYSTEM selector](../../src/pring_cycle/search_evidence.py#L79)也对 core 使用直接 SYSTEM 仓库。
- `build_context_projection`[不传 target_business_date](../../src/pring_cycle/context_projection.py#L233)时可以测试 SYSTEM 派生逻辑，但必须明确这是当前系统已知维度。
- 指定 target 的上下文或 targeted selector 会经 [TargetBoundEvidenceRepository](../../src/pring_cycle/context_projection.py#L589)，连 SYSTEM 也要求目标日日末之前的非空 PUBLIC。故默认未知 PUBLIC 的 core 不能支持历史目标日 OMO 正例；既然上述显式合成声明公开入口已经存在，应使用它，不移除此门。

## 本次读取指纹

以下均为 2026-09-09 03:35:58 UTC 附近的工作树读取快照；主线后续修改不回写这些 hash。代码骨架未运行，现存公开测试也未重跑。

| 文件 | bytes | SHA256 |
|---|---:|---|
| `tests/models/test_candidate_admission.py` | 239631 | `bfd4306c991e552587f8c75cc22aeadf8997d00cddd492bf92b41901a66af2b0` |
| `src/pring_cycle/core_history.py` | 7944 | `bca200e5d2bdaab71fe3f819e7d0183f6b27bd3b13e2acae17ed64b879764d13` |
| `src/pring_cycle/source_adapters.py` | 14052 | `a9c0e5f7db4d822e61da40b6f623621b3bc85f942a0982d1823592648fb07a4d` |
| `src/pring_cycle/evidence.py` | 60796 | `d27332e14065b179f510c6253e06088f376341349657b598bc692070d9c35ec2` |
| `src/pring_cycle/context_projection.py` | 84654 | `1f094f4b545304d9b0ecc276d0d3325d3d7ef45e6cbf36bd9b02015d1255b2c2` |
| `src/pring_cycle/search_evidence.py` | 18220 | `81a6b6fdcb4482de7ae33d075eb0990fab9a7b2f1f8b51635d8153f0a0814bcb` |

唯一新增文件为本文；最终字节数、SHA256 和链接存在性校验在交付消息给出，不重新采集已变动源码指纹。

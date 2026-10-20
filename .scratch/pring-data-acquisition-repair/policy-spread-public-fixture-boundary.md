# DR007 政策利差：公开原件测试入口

2026-09-09，只读源码/既有样本研究。以下绑定 03:52:58 UTC 的工作树快照；主线后续改动不覆盖本报告指纹。未运行应用、测试、SQL 或网络。

**可直接复用现有新目录公共入口：**[`test_registered_interbank_acquisition_preserves_public_boundary`](../../tests/models/test_candidate_admission.py#L1772) 的 `public_known=True` 分支，使用公开 `transmission` → `acquire_scalars` → `ingest_context_scalars`。无需手工补 SQL 或绕过字段守卫；应在采集回调内明确设置合成 PUBLIC，让时间声明与 acquisition 的 normalized 一起保存。

## 独立值与期望

- [已存 CFETS 原文](evidence-13-dr007-followup/d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d)：`data.lastDate="2026-08-28"`，根 `records` 中唯一 `instrmntCd="DR007"` 的 `wghtdAvgRepoRate="1.3859"`；不是收盘字段 `clsngRepoRate="1.3806"`。单位 % 的既有独立核验见[字段审查](dr007-followup.md#L42)。原件 1425 bytes，SHA256 为完整文件名；本轮已重核。
- 两份官方 OMO 公告的 7 天操作利率均为 **1.40%**：[08-21 原表 L362](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/d5/d5673e8e4351bc2a1ff1afdcdd89da9ba2c3c7a8fe946c3cd463c164da0cd834#L362)、[08-28 原表 L362](evidence-13/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a#L362)。精确 URL、30798/31000 bytes、页头时间及哈希已在[上一样本文档](official-macro-derived-fixtures.md)核定，本轮不重新审其全页。
- 正确独立十进制期望：`(1.3859 − 1.40) × 100 = −1.41 basis_points`。误用 DR007 收盘值则为 `−1.94 bp`；应按 raw 字段身份拒绝，不能拿这个值替代加权利率。
- **08-21 和 08-28 利率相等，因此值断言不足以发现回退。**用新公告时和错误退回旧公告时都可能得到 −1.41；必须断言最新所选 claim 与派生父项 ID。

这份 CFETS 历史原文提供独立数值锚点，不是 TuShare 交付原件。其 `head.tstext=2026-09-07 17:49:01`、请求 `publishedTime=2200` 都不能证明目标日首次公开。下面 transport 返回的是合成 TuShare JSON，capture 创建的是这次隔离测试的实际请求记录与制品，不冒充真实历史 HTTP 回执。

## 最小既有公开采集构造

在独立 runtime 中按同测试的 `prepared_request`、`submit/save` 建立合成审查的新目录，取得其 `version`、`model_id` 和 manifest。以下代码骨架未执行：

```python
from dataclasses import replace
from datetime import UTC, date, datetime
import json
from pring_cycle.tushare_context import TushareContextAdapter

day = date(2026, 8, 28)
public_at = datetime(2026, 8, 28, 8, tzinfo=UTC)  # Explicit synthetic test time.
responses = {
    "repo_daily": {
        "code": 0,
        "data": {
            "fields": ["ts_code", "trade_date", "repo_maturity", "weight"],
            "items": [["DR007.IB", "20260828", "DR007", 1.3859]],
        },
    },
    "shibor": {
        "code": 0,
        "data": {
            "fields": ["date", "on", "1w", "3m"],
            "items": [["20260828", 1.339, 1.387, 1.43]],
        },
    },
}

def transport(payload):
    api = payload["api_name"]
    assert api in responses
    expected = {"start_date": "20260828", "end_date": "20260828"}
    if api == "repo_daily":
        expected["ts_code"] = "DR007.IB"
    assert payload["params"] == expected
    assert payload["fields"] == ",".join(responses[api]["data"]["fields"])
    return json.dumps(responses[api], separators=(",", ":")).encode()

adapter = TushareContextAdapter("synthetic-token", transport=transport)

def retrieve():
    scalars = adapter.transmission(start_date=day, end_date=day)
    assert all(s.release_at is None and s.public_available_at is None for s in scalars)
    return tuple(
        replace(s, release_at=public_at, public_available_at=public_at)
        for s in scalars
    )

imported = adapter.acquire_scalars(paths, retrieve, definition_version=version)
```

[`transmission`](../../src/pring_cycle/tushare_context.py#L603)固定调用 `repo_daily` 和 `shibor`；这条现成 seam 为 **两个 transport 调用、两份物理回执、四个标量**，不是单请求 DR007 接口。测试只消费 DR007 与政策率即可，仍保留另外三条 Shibor 的正常接收。Shibor 合成值与[既有官方 JSON](evidence-13/365f18b1a160570e6d0762040bf6af670379be2946bec553593d2cbae3881f62)一致，但不参与政策利差；该原件 2112 bytes，本轮 hash 已复核。所有外部请求为 0；adapter 的请求计数仅表示调用了注入 transport。

## 回执、normalized 与 SourceClaimInput 如何关联

1. [`acquire_scalars`](../../src/pring_cycle/tushare_context.py#L152)在 `retrieve()` 返回后，按 scalar.api_name 关联已捕获回执；然后 `complete_validation` 将**带合成 PUBLIC 和 acquisition_ids 的最终 scalars**写入每份回执的 normalized，再调用公开 `ingest_context_scalars`。单日 DR normalized 是一个含 DR007 scalar 的数组；Shibor normalized 是另外三个 scalar，不混成官方 release 对象。
2. [`ingest_context_scalars`](../../src/pring_cycle/tushare_context.py#L1221)要求新目录 DR007 使用 `api_name=repo_daily/source_field=weight`。生成 `source_reference="tushare:repo_daily:weight:2026-08-28"`；[`SourceClaimInput`](../../src/pring_cycle/tushare_context.py#L1331)由其构造：`provider=tushare`、单位 percent、空维度、business_day 起止同日；fetched_at 取关联 received_at，available_at 先取 validated_at，append 的 availability_clock 再记录实际可用时钟，acquisition_ids 完整继承。
3. 不要在 `acquire_scalars` 完成后仅重写 claim PUBLIC、或重新构造与 normalized 时间不一致的 certified 声明来制造正例。应像已有测试一样在回调内设置合成时间。未设置时 PUBLIC 必须继续未知；取得时间不是发布时间。
4. 多日扩展时，当前按同 API 将 scalar 关联该批所有匹配回执，回执 normalized 可能含联合批次；不能为追求单行等长，拿某个 raw 响应与所有 normalized 标量生硬一对一。此最小单日测试只包含一份 repo_daily 回执，先避免改变批次契约。

公开验证依次用 `EvidenceRepository.metric_series` / `trace` 和 `AcquisitionRepository.history` / `read_content`：DR 值=1.3859、空维度、percent、provider=tushare、准确 source_reference、PUBLIC=合成 public_at、`acquisition_status=linked`。再用 `source_claim_acquisitions_many((dr_claim_id,))` 验证唯一 repo_daily 回执及 raw/normalized 内容；DR claim 不能错误挂到 Shibor 回执。PUBLIC 在 public_at 前不可见、在该时刻可见；SYSTEM 在本轮取得并校验完成后可见。[已有公共断言](../../tests/models/test_candidate_admission.py#L1823)可直接复用。

新目录字段与时期守卫仍生效，见[interbank 契约](../../src/pring_cycle/source_contract_review.py#L289)。`select_retrieval_input(paths, run)` 的历史目标 SYSTEM 也受目标 PUBLIC 上界限制：public_known=False 时不能通过，现有[定向选择断言](../../tests/models/test_candidate_admission.py#L1867)已明确这一边界。不能删该门让真实 PUBLIC 未知的 DR007 输入历史政策利差。

## 政策利差的公开断言与反例

保留 manifest 中 `dr007_policy_spread="dr007-policy-spread-v0001"`，通过 `ingest_official_context_document` 正常导入 08-21、08-28 两份 OMO 公告，使用新目录 version，不手改原表1.4。调用 `build_context_projection(..., target_business_date="2026-08-28", as_of=取得后当前时刻, as_of_mode=SYSTEM, persist_derived=True)`；历史 PUBLIC 正例另用中国 08-28 日末 cutoff。原 OMO 页头为各日 09:20:30+08；DR007 的 16:00+08 明确是合成测试时间。

| 场景 | 应断言的公开结果 |
|---|---|
| 完整正例 | transmission evidence 中 `CN_DR007_POLICY_SPREAD` 的 period=2026-08-28、unit=basis_points、value≈−1.41；`input_observation_version_ids` 精确为 DR007 当日 claim 和 **08-28 OMO rate claim**，不含 08-21 rate、OMO amount 或 Shibor。`derived_trace` 同样绑定这两个父项。浮点输出可用 `pytest.approx(-1.41, rel=0, abs=1e-12)`；独立期望本身用十进制计算。 |
| 坏最新 OMO normalized/raw | 先证明 pristine 正例，再破坏 08-28 回执指定制品。原报卡片可保留诊断值，但不得继续产生合格政策利差；不得采用坏 claim，也不得改用 08-21 rate 继续给 −1.41。不能只检查数字“未变”。 |
| 最新 OMO quality=invalid | 通过公开 `append_source_claim` 追加同一期、同值、同源、相同 acquisition 关联和原发布时间的 invalid 最新状态，保持 fetched_at 对应 received_at、available_at 为追加时刻；在该状态可见 cutoff 后，应有缺口。不能因为先筛 quality 再取最后一条而回退 08-21。先通过公开 series 确认 invalid 版本确实成为所选版本，避免测到未生效记录。 |
| 最新合法无利率列日 | 与坏已发表利率事件区别：没有新利率的真实零操作日可以继续消费此前合格政策率，不强求每日新增 rate claim。旧事件可用与“坏新事件被回退”分别验收。 |
| DR007 无 PUBLIC | 普通 SYSTEM 仓库可保留已取得原报值；历史 target 投影/检索和 PUBLIC 利差仍缺父项，不能用 OMO 的已知时间替 DR007 定时。 |
| 坏 DR normalized/原件 | 作为下一独立资格反例，原报、检索、派生及回放不得采用该坏输入；不能因该父项卡片 source_failed 而让派生重新直接从 series 取值。此项本轮只提出设计，未声明当前代码已做到或已复现失败。 |

当前快照 [`_latest_certified_point`](../../src/pring_cycle/context_projection.py#L1349)先过滤 `_certified_point` 再取最后一条；政策利差[直接调用两次并做差](../../src/pring_cycle/context_projection.py#L854)。它没有在这个函数内调用官方原件资格 helper，也没有 DR007 原件/normalized 重解析检查。因此上述坏最新与坏父项是具体静态风险，应从公开投影建立 RED；扩展原报卡片校验本身不能证明派生也合格。现有[旧目录政策利差测试](../../tests/integration/test_context_projection.py#L1181)仅适合借用结果/父项断言，其手写 synthetic provider 和 monkeypatch 方式不能原样当作新目录入口。

## 快照与交付

| 输入 | bytes | SHA256 |
|---|---:|---|
| `tests/models/test_candidate_admission.py` | 247783 | `82e9b8d16a9b2be3c72f027f0e921dfb9ae0d0b72baaa3ad79cdd9452efb7297` |
| `src/pring_cycle/tushare_context.py` | 76846 | `5a642d4a7275c8991d76f6e5ec24f271ff1fc8693e213fc7abeca26d0602c443` |
| `src/pring_cycle/source_contract_review.py` | 14630 | `c26ee6a06e25dc7b9b3c4c102bc9ce3e780dbc538760ef9318409d28f5ab9772` |
| `src/pring_cycle/context_projection.py` | 86059 | `1a6bd1bf7530afa2b3c68521c5962e6fd04ae38717e3c4a9d5ad8ff53a31fe83` |
| `tests/integration/test_context_projection.py` | 59768 | `82e2c192745e43088a120bc831c67090b9f920cd4ad361e60ce8b4027e2e2a19` |
| `dr007-followup.md` | 11885 | `8c8776372ecd26ca849275680d8368b73980678d3d5da9504f178a707ae9b462` |
| `official-macro-derived-fixtures.md` | 13757 | `160e6b6dd74b71080507c25d0a635969625c65ae1e58573916789751ec4b2b47` |

两份 CFETS 原件共 3537 bytes，本轮 2/2 hash 与文件名相符；已用标准库 Decimal 独立复核 −1.41/−1.94。唯一新增文件是本文，不新增原件或请求，不授认证。最终 bytes、SHA256 和本地链接校验结果见交付消息；不重采正在变化的源码指纹。

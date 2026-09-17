> **本记录描述的实现已于 2026-09-17 同日整体撤回。** 标准轴复审指出并经核实：`CONTEXT.md` 早已把"只有发布日期时从下一本地日开始"定义为「公开可用时间」的语义，`publication_times()` 早已实现它；新增的列冗余，且其默认值会把日期路径写入的既有声明错标为"来源实际发布过"。撤回理由见[核实记录](review-26-standards-findings-20260917.md)，票26 的新范围见[票面](issues/26-presumed-public-time.md)。
>
> 以下保留为当时的推演与失败经过，**不描述当前代码**。

# 票26：保守推定的 PUBLIC 时间（2026-09-17）

用户 2026-09-17 决定：拿不到发布时刻时，PUBLIC 可见时间推定为公告日次日 00:00，但必须写明是保守推定而非官方认证。本记录把该口径钉成可查行为。

## 现状：未知就是不可见

改动前，发布时刻未知的声明存 `public_available_at=None`，而 PUBLIC 查询明文排除 NULL（`evidence.py` 的 `AND {time_column} IS NOT NULL`）。这本身是诚实的——不知道何时公开，就不在 PUBLIC 模式下出现——代价是这些值**完全用不了**，票13 的 B 类 3 项与 C 类 2 项因此停摆。

## 落地的三件事

**一、`presumed_public_time(announced_on, release_timezone)`**

返回公告日次日 00:00 在该指标发布时区的瞬间，转为 UTC。时区取自目录的 `release_timezone`（中国指标为 `Asia/Shanghai`），不是硬编码——伦敦发布的指标拿伦敦的午夜。

推定**只会把可见时间往后推**，不会让未公开的值被提前采用。这是它能够代替真实发布时刻的**唯一**理由，也是记录里必须写明的那一句。

**二、`public_time_basis` 成为证据模型的一等字段**

取值两个：`observed_release`（来源确实发布过这个时刻）与 `presumed_next_day`（推定）。

- 写入 `SourceClaimInput`，存入 `source_claim` 表新列，读回 `ClaimView`——**投影与报告读的就是 `ClaimView`**，所以推定身份沿整条读取链可见，不是藏在采集回执或注释里。
- 旧的 `publication_precision` 只是 `worker.py:1398` 的一个回执 kwarg，承担不了这件事，未改动它。

**三、两条校验**

- `public_time_basis` 不在允许集合内即拒绝——不接受任意字符串。
- 标为 `presumed_next_day` 却没给时间的声明被拒绝（`evidence_presumed_public_time_required`）：那种声明既没记录任何东西，又掩盖了它曾试图推定。

## 验证

新增 `tests/evidence/test_presumed_public_time.py`，3 项通过/0.4 秒：

- 公告当日 23:59（上海时间）该值**不可见**，次日 00:00 起可见；
- 推定身份在 `ClaimView` 上读得到；
- 真实发布时刻的声明**不被标成推定**，且从发布那一刻即可见，不被额外延迟一天；
- 推定瞬间按各指标自己的时区计算（上海 UTC+8 → 公告日 16:00 UTC；伦敦 → 23:00 UTC）。

**变异检查**：把推定改成公告日当天（去掉 `+1 天`），两项用例立即变红——`assert (-0.5,) == ()`，即公告当日的值变得可见。说明用例确实在检验这条行为，不是摆设。

## 一次撞上架构不变量的失败

第一版实现把新列直接加进了 `_EVIDENCE_SCHEMA` 的 `CREATE TABLE`，回归 **820 失败 / 181 通过**，错误是 `migration_0002_schema_snapshot_changed`。

原因：`_EVIDENCE_SCHEMA` 是 **v1 冻结快照**，迁移 0002 对它逐字节取 sha256 并与写死的哈希比对，不符即拒绝启动。改基线等于宣称"v1 当初就长这样"——那是假的，会让所有历史库的 schema 溯源失效。守卫做的正是它该做的事。

正确做法（仓库既有惯例）：基线不动，后加的列**走基线之外**。`_initialize` 本来就在冻结脚本之后执行 `_RELEASE_EVENT_EXTENSIONS_SCHEMA` 等扩展；但 SQLite 没有 `ADD COLUMN IF NOT EXISTS`，纯脚本无法幂等，所以新增 `_add_public_time_basis()`：读 `PRAGMA table_info` 后按需补列。

于是两条建库路径汇合：

| 路径 | 如何获得该列 |
|---|---|
| `initialize_runtime`（正式运行库） | 迁移 `0022` |
| `EvidenceRepository.create`（测试与独立库） | `_initialize` 中的 `_add_public_time_basis` |

**这是 `source_claim` 上第一个 v1 之后的列**，所以没有现成先例可抄——先例是这次建立的。

## 迁移

`0022_presumed_public_time`：给 `source_claim` 加列，默认 `observed_release`。

**默认值不是在给旧数据贴标签**——既有声明的 `public_available_at` 全都来自来源实际发布的时刻，默认值陈述的是本来就成立的事实。读回时对 NULL 也回退到 `observed_release`，兼容未经迁移的库。

## 相关回归

`tests/evidence`、`tests/maintenance`、`tests/models/test_candidate_admission.py`、`tests/integration/test_retrieval_ledger.py`、`tests/adapters`：**1001 通过 / 0 失败 / 28:54**。修正前同一批是 820 失败 / 181 通过。

`ruff check`（src+tests）、`ruff format --check`（本批 4 个文件）、`mypy src` 97 源文件均通过。仓库另有 13 个文件与当前 ruff 版本存在既存格式差异，非本批引入。

一处如实记下：格式化 `evidence.py`（仅增一个空行）发生在这批 pytest 启动之后。模块在进程启动时已导入，行为不受影响，但该批结果对应的文件与当前树差一个空行。同版本冻结全套会在统一版本上重跑，以那次为准。

## 范围

本票**不认证任何来源**，也不解除票13 对官方原件的记录：取得真实发布时刻后仍应改用它，届时旧判断按 [ADR-0006](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md) 的不可变 vintage 保持不变。

本票也**没有**把推定应用到任何具体指标——那是票13 各家族认证时的动作。这里只建能力。

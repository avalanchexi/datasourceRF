# 票26 两轴复审：我的实现应当撤回（2026-09-17）

固定点 `eae3e41~1`。标准轴给出两条硬结论，我逐条核实，**两条都成立，且合起来说明整个实现是多余的**。

## 一、这个概念 `CONTEXT.md` 早已定义，且我用了它明令避免的词

> **公开可用时间（Public Available At）**：来源声明按可靠官方发布时间进入公开点时查询的保守时点；**只有发布日期时从下一本地日开始**，无可靠日期时为空。
> _Avoid_: 计划发布日期、系统首次取得时间、**推测发布时间**

"只有发布日期就从次日开始"**本来就是这个字段的定义**——它是保守时点的既定语义，不是新增的推定。而我引入的 `presumed_public_time` / `presumed_next_day` 用的正是术语表 `_Avoid_` 里的"推测发布时间"。

按 `docs/agents/domain.md`：术语应使用 `CONTEXT.md` 已定义的说法，遇到新词要先判断"是错误的新说法，还是确需通过 `/domain-modeling` 补充的领域概念"。**这里是前者。**

用户 2026-09-17 决定的"保守推定为次日 00:00"，**系统本来就是这么做的**。我把一条既有规则当成了待实现的新需求。

## 二、我重新实现了一个已经存在的函数

`presumed_public_time(announced_on, tz)` 与 `publication_times(published_at, tz)` 的日期分支**逐字节等价**，实测返回值相同：

```
publication_times(date(2026,4,19), Asia/Shanghai) -> (None, 2026-04-19 16:00:00+00:00)
presumed_public_time(date(2026,4,19), 'Asia/Shanghai') ->       2026-04-19 16:00:00+00:00
identical: True
```

两者相距 28 行，在同一个文件里。

## 三、更彻底的结论：那个区分本来就能推出来

`publication_times` 的三种返回形态天然编码了"时刻从哪来"：

| 情形 | `release_at` | `public_available_at` | 含义 |
|---|---|---|---|
| 来源给了完整时刻 | 有 | 同一时刻 | 来源实际发布时间 |
| 来源只给了日期 | **None** | 次日 00:00 | 按定义保守推到次日 |
| 无可靠日期 | None | None | 未知，不可见 |

**新列 `public_time_basis` 因此是冗余的。** 更糟的是它的默认值把第二类错标成 `observed_release`（"来源实际发布过这个时刻"）——`official_context.py:230` 与 `official_lpr.py:148` 都走日期路径，它们写入的既有声明会被这个默认值说成是观测到的发布时刻。**这正是该特性本该防止的那种失真，却由我引入。**

## 四、其余发现（判断项，随撤回一并失效）

- **Speculative Generality（真）**：`PRESUMED_NEXT_DAY` 没有任何生产调用方，只有测试在写。
- **Primitive Obsession**：两个封闭取值用裸字符串 + 手写成员检查，而紧邻就是 `EvidenceValueState(StrEnum)` 这个先例。
- **校验不闭环**：`_validate_claim` 手上有 `definition.release_timezone`，却从不检查标为推定的声明其时间是否真等于次日 00:00——标签无人执行。
- **`_add_public_time_basis` 与迁移 0022 已经漂移**：前者插值 `{OBSERVED_RELEASE}`，后者硬编码字符串。
- **`test_official_fallback_candidates.py` 是变更探测器**：`WITHOUT_A_FALLBACK_PAGE` 只是复述当前目录常量，且它属票25 而非票26。

## 处置

等需求轴裁定后一并处理。若需求轴同意，`eae3e41` 应当**撤回**：删除新函数、新字段、新列、迁移 0022 与 `tests/evidence/test_presumed_public_time.py`。

**票26 本身要重写**：它真正未解决的只剩 `CONTEXT.md` 里"无可靠日期时为空"那一类——连可靠日期都没有的历史首次公开时间（票13 的 DR007）。改变那条规则是**领域语言变更**，要走 `/domain-modeling` 并修订 `CONTEXT.md` 或写 ADR，不是悄悄加一个字段。

## 附带代价

任务 D 的同版本冻结全套在本结论出来时跑到 21%，已主动终止——在即将撤回的代码上跑两小时是浪费。撤回后需重跑。

---

# 需求轴：独立抓到**另一个**真缺陷

需求轴复审的是撤回前的状态，裁定**票26 不能勾选**，四条验收条件中第 4 条不满足——而它指出的问题与标准轴完全不同：

## 迁移改写了运行库的健康状态

`storage.py:15` 的 `SCHEMA_HEAD = "0021_context_replay_outputs"` **没有随迁移 0022 一起更新**，而 `migrate_database` 执行 `command.upgrade(config, "head")`。于是每个走正式迁移的库会落到 `0022`，`database_health()` 随即判定 `migration="outdated"`、`status="degraded"`。

**这不是测试口径问题，是正式运行库的健康状态被这次迁移改坏了。**

连带两处用例必然变红，而它们都**不在我当时跑的回归范围里**：

- `tests/integration/test_database_lifetime.py:147` 断言 `database_revision == '0021_context_replay_outputs'`
- `tests/integration/test_rehearsal_cutover.py:650` 断言 `manifest["database_revision"] == SCHEMA_HEAD`

被我终止在 21% 的那次同版本冻结全套**本来会抓到它**。撤回后 `SCHEMA_HEAD` 与最新迁移重新一致（均为 `0021`），该缺陷随之消失。

## 需求轴对其余各项的裁定

| 项 | 裁定 |
|---|---|
| 验收条件 1、2 | 满足（推定可回溯、公告当日不可采用，变异检查有效） |
| 验收条件 3 | **部分满足**——变异检查针对的是 `+1 天` 而非标注本身，"去掉标注会失败"没有实际变异佐证 |
| 验收条件 4 | **不满足**，即上述 `SCHEMA_HEAD` 问题 |
| 是否越界 | 无。`worker.py` 未改，没有任何指标被实际标为推定，符合票面"只建能力" |
| 票25 "Blocked by 19" | **成立**。`source_candidates` 是定义字段，没有绕开目录版本的小路 |
| `test_official_fallback_candidates.py` | 第一条**接近同义反复**（从目录算出集合再与写死集合比对），价值仅限"名单缩小必须显式改"这一棘轮；第二条（同族不得指向不同页）是真约束 |
| 探测诚实性 | **通过**。参数被遵守，失败如实记为未取得，`CN_USDCNY_CLOSE_1630` 的口径自纠属实 |
| 多余改动 | 无 |

## 探测记录的一处缺陷（需求轴指出）

冻结参数要求"间隔 ≥2 秒"，但 JSON 里记的 `seconds` 是**单次耗时**（0.13/0.15/0.16），不是间隔——**该参数无从对账**。脚本里确有 `time.sleep(2)`，但记录没留下可核验的证据。下次探测须记请求时间戳而非耗时。

# 两轴各抓到一个，且互不重叠

| 轴 | 发现 |
|---|---|
| 标准 | 概念早已在 `CONTEXT.md` 定义、函数早已存在、新列冗余且默认值错标既有声明 |
| 需求 | `SCHEMA_HEAD` 未同步，正式运行库健康状态被改坏 |

**任一轴单独放行，都会漏掉另一轴的那个问题。** 这是两轴分开评审的直接价值，也是本次最值得留下的一条经验。

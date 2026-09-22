Status: software-slice-complete
Type: implementation
Date: 2026-09-22
Ticket: 05

# 票05 软件切片：沪深两所融资身份迁移

按 2026-09-22 用户决定（见票05 `## Comments`）与
[ADR-0016](../../docs/adr/0016-certification-gate-escape-valve-is-catalog-membership.md) 实施。
**这是软件迁移切片，不是来源认证**；本切片未勾选票05 任何验收条件。

## 实施前查实的一条事实（改变本切片的价值）

`research-05.md:114`：「**SSE、SZSE、BSE** 的目标 120 日均未由现有原件证明实际首次公开链」——
缺公开时间证据的**不只北交所，沪深同样缺**。`:93` 又记明 TuShare 的「次日上午更新」只是交付安排，
按 [ADR-0018](../../docs/adr/0018-tiered-evidence-for-historical-publication-dates.md) 那属「预期发布窗口」，
不得充当公开时间。

**因此新身份并不因本切片变得可认证**：它消掉了北交所的数值缺口，沪深的公开时间缺口原样存在。
按 ADR-0016，未认证的 P1 进不了候选，**票19 的真实完整候选仍卡在票05 的来源认证**。
**但这句要说准**：票19 票头自述「这里**不等待**上述来源认证整票」，它的*软件*路径本就不等票05，
所以本切片既没解锁、也不是票19 软件侧的前置。本切片交付的是身份本身。

## 改了什么

| 文件 | 改动 |
|---|---|
| `metric_contracts.py` | 新增 `CN_MARGIN_BALANCE_SSE_SZSE` 的必需成员，`scope: "sse_szse"` × 两个 measure |
| `candidate_admission.py` | 新增 `_MARGIN_SCOPE_MIGRATION` 声明并在 `_admission_catalog` 中处理；旧 `CN_MARGIN_BALANCE` 移出新目录 |
| `evidence.py` | 内联的替换身份集合提为私有常量 `_MIGRATED_IDENTITIES`，并纳入新 id |
| `candidate_admission.py` | 新 id 登记进漂移闸身份表；baseline 的非身份字段改取自清单 |

沿用 #27 建好的迁移机制（清单内 `metric_identity_migration` 精确白名单），未新造第二套。
新身份仍是 **P1**（未降级），P1 总数保持 42。

## 反例抓到的真实缺陷

第三条用例最初 **DID NOT RAISE**：旧的三所合计声明**可以只改 id 就挂到新的两所身份上**，
因为 `evidence.py` 的交付契约闸只对 `certified` 声明或一张**硬编码的替换身份表**生效，
新 id 不在表内。这与 #27 当初在 TMA 上发现的是同一个洞（见
[implementation-27](implementation-27-identity-migration-20260917.md)「未认证声明原本绕过来源契约」）。

修法：把那张内联集合提为 `MIGRATED_IDENTITIES` 常量并加入新 id——它在长，内联下去下次还会漏。
现在新身份即使未认证也必须经过自己的交付契约，而该契约尚未实现，故一切冒名继承被拒。

## 复审又抓到第二个同类洞（准入侧）

标准轴指出 `candidate_admission.py:200` 另有一张**漂移闸身份表**，只登记了 TMA 与 ECB。
实测反例确认：清单用**新 id 配旧 `source_codes`** 可以直接过准入（`status: candidate`）——
`evidence.py` 侧堵住的"只改 id 就冒名"，准入侧原样敞着。这与上一节是同一类缺陷的两个出口。

修法与踩到的坑：把新 id 登记进该表后，原有两条用例转红。原因是**清单里的融资定义比
`metric_catalog()` 的存根丰富得多**（`hundred_million_cny`、带 `measure`/`scope` 维度、
`tushare:margin` 候选），而普通指标根本不比这些字段——把融资塞进漂移闸，等于拿存根去比真实清单。
最终让 baseline 的**非身份字段**取自清单自身，只强制身份字段（`name_cn`、`source_codes`、
`release_event_family`），闸因此比的是"这是哪条交付"，而不是重新审一遍整个形状。
新增用例 `test_the_new_identity_cannot_keep_the_retired_source_path` 钉住这条。

## 验证

- 专项 `test_margin_scope_migration.py` **5 passed**（含两条准入侧身份反例）
- 相关回归（迁移/认证/预检五文件）**68 passed / 118.59 秒 / exit 0** →
  `verification-05-margin-scope-related-20260922.txt`
- `test_candidate_admission.py` 重型专项 **654 passed / 1375.98 秒 / exit 0** →
  `verification-05-admission-20260922.txt`（C 盘运行前后均约 68 GiB，未触发磁盘保护）
- Ruff check / format、mypy 三源文件均通过

## 未交付（不得据本切片声称已完成）

- **沪深历史公开时间证据**——票05 的真正剩余阻塞，按 ADR-0018 只认逐版本发布证据
- `CN_MARGIN_BALANCE_SSE_SZSE` 的**采集适配器与交付契约**（当前故意缺位，靠它拒收冒名）
- 旧三所身份的历史声明保留可追溯，**未回写、未拼接、未产生残差**
- **「北交所作为已知缺口显式记录」只落在散文里**：代码与数据中没有缺口条目，也没有承载它的机制。
  本切片未发明一个，此项记为未交付。

## 遗留（本切片未处理，留给后续）

1. **`source_certification.py:44` 的 `_TUSHARE_MARKET_P1` 仍列 `CN_MARGIN_BALANCE`**，
   而迁移后的目录已无此 id。今日不报错（`:126` 取的是内置 `metric_catalog_v0003()`），
   但票19:40 要求的「15 项市场 P1 注册合同交付」清单已因本次迁移变陈旧，须随票19 交接一并订正。
2. **迁移知识仍散在四处**（白名单、目录改写分支、漂移闸身份表、`_MIGRATED_IDENTITIES`）。
   第 4 条迁移仍要改多处；应改为表驱动、让声明自带其目录改写与身份约束。白名单本身应保留——
   它闸的是不可逆目录变更，穷举是特性不是缺陷。本切片未做此重构。

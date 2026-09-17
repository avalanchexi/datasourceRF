Status: ready-for-agent
Execution: not-started
Scope: 来自[规格24](../spec-24-source-identity-20260917.md)第三、四节
Decision: 2026-09-17 用户确认：USD/CNH 改用 TMA 定盘并重命名；删除 COMEX_GC 与 LBMA_GOLD；VIX/SOX/USDCNY_CLOSE_1630 走各自官方通道。

# 27: 修正五项 P2 国际行情的口径与身份

**What to build:** P2 国际行情各项的口径与其实际发布方一致；不再有指标 id 把上游代码或经纪商名字当作标准口径。

**Blocked by:** 无。

**Dependency rationale:** 独立于票25、26；三张票可并行。

## 逐项动作

| 指标 | 动作 | 依据 |
|---|---|---|
| `CN_USDCNH_FXCM` | 改用香港财资市场公会（TMA）USD/CNH 即期定盘，**重命名去掉 FXCM** | 离岸人民币无单一官方即期价，TMA 定盘最接近基准；原 id 的 FXCM 来自 TuShare 标的代码 `USDCNH.FXCM`，属沿用上游代码时继承的缺陷 |
| `COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT` | **删除** | 与 LBMA 金价高度重叠，历史批量需 CME DataMine 付费 |
| `LBMA_GOLD_PRICE_PM_USD_OZT` | **删除** | 历史需 ICE Benchmark Administration 授权，只能走 FRED 转发；为一项 P2 背景指标建整套非官方身份语义不划算 |
| `CBOE_VIX_INDEX` | 接 Cboe 官方免费 CSV，正常认证 | TuShare `index_global` 的 20 个指数不含 VIX |
| `NASDAQ_SOX_INDEX` | 接 Nasdaq 官方指数站，正常认证 | 同样不在 `index_global` 内 |
| `CN_USDCNY_CLOSE_1630` | 接 CFETS / 中国货币网，正常认证 | 本项目已有该域通道（`CN_LPR_1Y_5Y` 走同一域且已认证） |

## 待设计的可观察行为

- 指标 id 是身份的一部分：**重命名与删除必须作为迁移设计**，波及目录版本、历史声明与投影。旧 id 的历史证据如何处置须显式表达，不得静默丢弃。
- 新接的三项走既有认证流程，**不引入新的认证身份**——`certification_status` 保持 `certified` / `awaiting_source_certification` 两值不变。

## 验收条件

- [ ] 重命名后旧 id 的历史声明可追溯，且新旧不混算；有反例证明混算会失败。
- [ ] 删除两项黄金指标后，依赖它们的派生与投影路径明确报错或明确不再需要，不留悬空引用。
- [ ] VIX / SOX / USDCNY_CLOSE_1630 各有取得原件与认证材料，走既有认证流程。
- [ ] `certification_status` 取值集合不变。

## 未核实

Cboe CSV、Nasdaq 指数站、TMA 定盘的当前可达性与可程序化取用方式。实现第一步应先核实，取不到则该项保持未认证而非降级冒充。

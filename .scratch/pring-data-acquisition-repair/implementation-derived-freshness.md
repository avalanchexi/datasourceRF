Execution: completed-code-batch

# 13/14续：派生结果保留真实鲜度

基点 `68c87eaef1fa21ef62f74400f6c9b8e772fbf0ec`，范围见[本批边界](derived-freshness-boundary.md)。
本批修复已有日频10、月频95、季频190自然日等后备阈值被派生计算绕过的问题；
不是独立官方发布日历与宽限期的完成。

## 行为与证据

UST、DR007、两项PMI差值、贷款变化、OMO的终止期按照模型绑定的实际父项频率判断。
信用脉冲分别核对最新社融月和GDP季，24月/8季必要预热仍可参与计算。
陈旧结果保留数值、真实期次、不可变父项与派生血缘，但标为`stale`，
从当前支持证据及模型采纳中排除；信用公式额外显示“输入数据已陈旧”。
较早生效的政策利率不单独把当前DR007利差判旧，PMI差值不误用旧输出目录中的日频默认。

公开投影/存取/追踪接口测试使用隔离fixture，不伪造正式认证。独立算例包含：
美债4.73%-4.34%=39bp，DR007 2.2%-1.5%=70bp；PMI订单52、生产51、库存48
对应4/-1点；贷款110-100=10；OMO3000-2500=500；信用36/120-24/100=6个百分点。
近期和旧期均保留这些值，只有近期派生结果可以成为当前模型输入。

## 验证流水

- [UST RED](verification-derived-freshness-red-ust.txt)：1失败/1通过，1.35秒，旧期错误为current；[修复](verification-derived-freshness-green-ust.txt)2通过，0.91秒。
- [宏观 RED](verification-derived-freshness-red-macro.txt)：6失败/8通过，2.88秒，6公式旧期错误为current；[修复](verification-derived-freshness-green-macro.txt)14通过，2.69秒。
- [信用 RED](verification-derived-freshness-red-credit.txt)：4失败/16通过，4.45秒，分别覆盖SF/GDP终止期与PUBLIC/SYSTEM。
- [第一次信用GREEN](verification-derived-freshness-green-credit.txt)：4失败/16通过，5.71秒。鲜度、公式状态、真实期次和采纳断言已经通过，失败来自测试误写领域状态`unconfirmed`；实际公共状态为`insufficient_data`。此错误属于测试设置，不是新产品缺陷。
- [关联测试](verification-derived-freshness-focused.txt)：63通过，11.91秒。此后将无区分力的信用总状态断言改成直接检查同一派生ID在过热支持/缺口中的归属；[最终20项](verification-derived-freshness-signals.txt)通过，4.07秒。应用代码未再改变。
- Ruff通过、mypy84文件通过，[81安装Python源文件](verification-derived-freshness/code-fingerprint.json)与工作区一致；使用规定WSL非editable环境，重新安装等待退出0后才测试。
- [双轴审查](verification-derived-freshness/review.md)：Spec0、Standards0；最后解释断言增量也通过。
- 本批全套一次运行，**702通过、0失败、758.10秒**，退出码0；[完整日志](verification-derived-freshness-pytest-20260908-a.txt)、[最终收据](verification-derived-freshness/final.json)。3文件format check通过。

本批没有真实HTTP/Tavily/Exa请求、生产写入、来源认证授予、新候选模型或模型生效/切换。
旧目录和已有发布结果不覆盖；新正式运行继续受来源契约和新模型验收门禁约束。

同期[P2鲜度研究](p2-freshness-evidence-boundary.md)区分当前源观察与历史目标时点资格，
以及EIA计划日期和实际发布。根代理只读标准库[校验](verification-derived-freshness/research-verification.json)
确认报告9295字节/精确SHA、14个本地链接、5份原件1075543字节；原件无变更。
该报告建议的当前源观察比较尚未实施，不能据此改变历史PUBLIC或鲜度。

同期[CPI两指标逐值审查](p1-cpi-full-value-audit.md)完成8期46格。根代理独立使用标准库HTML表格解析，
逐一复核报告的原件/表行列/源码行号、字面期望、准备快照数值/类别/月份/单位；46相符、0冲突，
8原件1850811字节及13链接通过，见[只读复核](verification-derived-freshness/cpi-verification.json)。
这比旧18个代表性锚点多完成44个不同标量，原1858标量中已有62个独立核对，另1796个仍待逐格审计；
没有改写旧不可变准备包或将其PUBLIC时间认证通过。

在全套运行期间独立复现[贷款YTD一月跨年缺陷](loan-ytd-year-boundary.md)，2项RED均失败；
它尚未修复、不在本批默认测试目录覆盖中。下一批直接从该公开反例续作，不能因702通过而漏掉。

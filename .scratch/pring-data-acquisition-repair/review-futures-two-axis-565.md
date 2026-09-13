# 票11首次两轴WIP审查汇总565

以下为固定565快照的两份独立报告；后续修复另见实施记录，不改写本次审查结论。

## Standards

基点：`5e186f740be3d275cba5664a13ef0290e6a57916`；提交列表为空。审查命令：`cat .scratch/pring-data-acquisition-repair/futures-review-565/changes.patch`。三份源码及补丁 SHA-256 均与 `futures-review-565/manifest.json` 一致；仅审新增 `futures_inputs.py`、`test_futures_inputs.py` 及适配器新增方法，未纳入旧 WIP 538。

**硬规范违规：0。** 对照 `AGENTS.md`、`docs/agents/domain.md`、`CONTEXT.md`、ADR 0004/0006/0012/0013、`docs/development/local-runtime.md` 及规格 Testing Decisions，未发现本票有充分依据的硬违规。测试沿用公开采集、证据查询和已批准的时钟/transport 接缝；没有替换内部解析或校验。适配器转发属于 ADR 0004 明确的 TuShare 接缝，不列为 Middle Man。Ruff/mypy 可查项不重复报告。

**判断性建议：1 项，P3，possible Duplicated Code。** 冻结 `futures_inputs.py:177–193` 与 `209–225`（新增文件 hunk `@@ -0,0 +1,623 @@`）重复检查证据引用非空、去重、归属，以及相同的发布时间规则，包括：

```python
release, public = _time(item["release_at"]), _time(item["public_available_at"])
```

两处随后均调用 `publication_times(published, ZoneInfo("Asia/Shanghai"))` 校验仅日期精度。未来调整保守公开时点或证据引用约束时，漏改一处会使普通发布和夜盘时段采用不同规则。建议仅提取这段共同校验，保留各自身份检查；不需要全局重构或新增测试接缝。这是 smell 基线的判断性建议，不是仓库硬规则违规。

只读审查未运行测试；23 项专项通过属于上游提供的验证状态。本结论不代表真实来源认证完成，也不评价 Spec 轴。

## Spec

固定基点 `5e186f740be3d275cba5664a13ef0290e6a57916`；commit list为空。审查命令：`cat .scratch/pring-data-acquisition-repair/futures-review-565/changes.patch`。三份快照及补丁SHA-256均匹配manifest；仅审565增量，未读取另一轴，未运行测试或网络。下文F指[冻结源码](futures-review-565/futures_inputs.py)。

结论：4项错误实现、1项未完成软件条件；最严重的是矛盾输入被静默择一。以下均为静态路径判断，待公开边界反例确认。

1. **P1／错误实现：冲突输入失去冲突状态。** [规格](spec.md)要求“重复输入、矛盾修订、截断和未知时间必须有负例”。同一行情响应追加同合约同日、不同settle的行，F:336–364均接收，F:545只保留首行；两个已审批次同PUBLIC时间但不同settle也静默保留先入库值。应拒收批内矛盾、在跨批同点时冲突时报告缺口。根线程已开始处理批内重复；不代表565通过，也不能替代跨批检查。

2. **P1／错误实现：未来审查可提前成为SYSTEM输入。** [规格](spec.md)要求“显式 SYSTEM 查询不得提前可见”。把合法包的`reviewed_at`改到采集之后并重新保存审查哈希，F:146仅检查带时区；F:530–536只以获取收据校验时间计可用。9月8日采集可接受9月10日才审查的包，并在9月9日SYSTEM查询可见。须校验审查时序。

3. **P2／错误实现：空单位变成有效字符串。** [票11:17](issues/11-futures-contract-evidence.md)要求“核对结算/前结算、单位和日期”。保持合法合约与正价格，仅令`quote_unit=null`，F:89转为`"None"`，F:355–360仍标available，F:613也不报单位缺口；完整其余输入可返回missing=[]。缺失单位必须拒收或显式不可用；这不涉及12的注册合同。

4. **P2／错误实现：范围外损坏污染当前查询。** [票11:7](issues/11-futures-contract-evidence.md)要求“用户按日期查询篮子所需”输入。完整采集CU和PP后，仅损坏PP结算原件；SYSTEM查询CU仍在F:552–572验证PP并追加delivery_invalid，到F:574–592才过滤品种和日期。应先确定本次采用范围，再核原件；历史其他日结算亦有此问题。

5. **P2／未完成软件条件：日历区间缺口未列账。** [票11:21](issues/11-futures-contract-evidence.md)要求“提供12所需的已证输入范围和具体缺件”。F:458–467请求至到期日，但F:597–604只检查目标日；删除目标日之后、到期日之前的一条日历行，或把它改为null，并同步合法原件绑定，完整其余输入仍可missing=[]。缺行会影响12的10／11交易日边界；11应报告所交付区间缺件，实际选约仍属12。

未见scope creep。真实PP发布方样本、历史PUBLIC认证仍为已登记外部阻塞，不计软件bug；12选约、收益与注册合同不计本票遗漏。

Standards：硬违规0、判断性建议1，主要为重复校验；Spec：错误4、未完成条件1，最严重为矛盾输入被静默择一。

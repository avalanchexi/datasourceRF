# Standards — 565 冻结 WIP

基点：`5e186f740be3d275cba5664a13ef0290e6a57916`；提交列表为空。审查命令：`cat .scratch/pring-data-acquisition-repair/futures-review-565/changes.patch`。三份源码及补丁 SHA-256 均与 `futures-review-565/manifest.json` 一致；仅审新增 `futures_inputs.py`、`test_futures_inputs.py` 及适配器新增方法，未纳入旧 WIP 538。

**硬规范违规：0。** 对照 `AGENTS.md`、`docs/agents/domain.md`、`CONTEXT.md`、ADR 0004/0006/0012/0013、`docs/development/local-runtime.md` 及规格 Testing Decisions，未发现本票有充分依据的硬违规。测试沿用公开采集、证据查询和已批准的时钟/transport 接缝；没有替换内部解析或校验。适配器转发属于 ADR 0004 明确的 TuShare 接缝，不列为 Middle Man。Ruff/mypy 可查项不重复报告。

**判断性建议：1 项，P3，possible Duplicated Code。** 冻结 `futures_inputs.py:177–193` 与 `209–225`（新增文件 hunk `@@ -0,0 +1,623 @@`）重复检查证据引用非空、去重、归属，以及相同的发布时间规则，包括：

```python
release, public = _time(item["release_at"]), _time(item["public_available_at"])
```

两处随后均调用 `publication_times(published, ZoneInfo("Asia/Shanghai"))` 校验仅日期精度。未来调整保守公开时点或证据引用约束时，漏改一处会使普通发布和夜盘时段采用不同规则。建议仅提取这段共同校验，保留各自身份检查；不需要全局重构或新增测试接缝。这是 smell 基线的判断性建议，不是仓库硬规则违规。

只读审查未运行测试；23 项专项通过属于上游提供的验证状态。本结论不代表真实来源认证完成，也不评价 Spec 轴。

# 新模型的目标交易日与 SYSTEM 使用边界

依据用户 #26「保留历史缺口，按实际 SYSTEM 时间使用」和 #27 ECB 独立指标决定。领域已有
Available At / Public Available At；不新增数据库时间字段或改写领域定义。当前目标日 wrapper
对 SYSTEM 一律加 PUBLIC 过滤，导致已校验且满足认证条件的数据也无法使用。

沿用现有 `point_in_time_rule_version`，为新候选新增精确支持值 `dual-cutoff-v0003`。旧
`public-cutoff-v0002` 及旧模型缺省保持现状；新值必须经完整 manifest 绑定的候选准入，调用时
不能把旧 manifest 临时改一个字段取得新规则。遵守 ADR-0012，规则变化产生新模型。

令 A=运行 system_as_of，T=目标交易日上海时区日末。统计期边界和可见窗口仍按既有规则。

| 查询模式 | 来源声明可见条件 |
|---|---|
| PUBLIC | 可靠 public_available_at ≤ min(A,T)；NULL 仍不可见 |
| SYSTEM | available_at ≤ A，且 public_available_at ≤ T 或 available_at ≤ T |

后一条件保留已有历史手动运行对可靠公开日期的限制；同时允许当日已取得/校验的未知公开时间
或仅日期保守次日公开值使用 SYSTEM。历史 NULL-PUBLIC 在实际取得前的目标日仍缺口；当前
已取得历史值不会倒填进过去 SYSTEM 快照。公开回放规则与真实认证/质量/必需成员门均保持。

目标时点过滤必须发生在同一来源 vintage 选择之前，避免后来修订遮住在目标日可见的旧版本。
PUBLIC 和旧规则不改变。ECB 在 ModelInputSelector 加入原件来源复核，与投影保持一致；
原件/公式损坏、未认证、质量失败仍不能补齐模型输入。

公开 seam 沿用已同意的候选 CLI / ModelRepository、Acquisition / EvidenceRepository、
RunRepository / ModelInputSelector / build_context_projection，再接 Worker。先一个公开反例
到实现，再补历史边界、旧模型不变、修订、来源完整性和实际完整运行。测试只控制外部时钟/HTTP。

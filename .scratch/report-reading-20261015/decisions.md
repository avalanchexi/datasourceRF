# 报告解读实施决定（2026-10-15）

用户在 Codex 接续会话确认：“按上述方向继续（推荐）”。本文件收束 Claude 尚未获答复的六问，供前端规格引用。

1. 非典型组合解读为 `sections` 内唯一固定标题“非典型组合解读”。CLI 输出 schema 不变；带新投影依据的报告提示词为 `report-prompt-v0006`。
2. Worker 在 `cycle_overview.noncanonical_basis` 写入全部“差一项资产”对照；复用六阶段映射表，不打相似度分、不选“最接近阶段”。债牛/股熊/商牛对应 I（商品）、III（股票）、V（债券）；反向组合对应 II（债券）、IV（商品）、VI（股票）。
3. 明确区分 `candidate_30d`（即时方向，无持续天数）与 `candidate_state` / `candidate_days`（趋势切换候选）。`persistence_required` 取本次模型的规则，不写死；无模型门槛的旧输入不编造门槛。
4. 内容是差异、候选、后续观察。正式阶段与阶段史仍完全由三核心决定，宏观五维继续按确定性投影展示。依据 GLOSSARY，不使用 Claude 初稿中的“最接近阶段”措辞。
5. 为使事实校验可机械复核，固定 section 须以 Worker 给定的全部事实句开头，然后由 AI 在给定的观察句中选择至少一句并组织次序，每句至多一次。不接受自行改写数字、阶段、候选，也不接受添加否定词后反转事实。非典型组合的新报告只接收这一段 AI 解读，避免其他 section 绕过对照校验；典型组合的解释段仍沿用现有规则。这是受约束的解读，不声称能校验任意自然语言语义。
6. 两个 CLI 均不可用或被拒时，使用同标题事实段（无观察建议），报告仍为 `completed_degraded`、adapter 仍为 `deterministic`，正文 `explanation_source=deterministic_template`；首页和报告页明确标“确定性模板”，不冒充 AI 成功。
7. 仅新投影/新运行启用。无 `noncanonical_basis` 的旧输入继续使用旧提示契约；旧投影、快照不回填。新报告的首页读取必须匹配 `projection_set_id`，同投影取最新报告版本。
8. 票 01 的留存由输入 bundle 所属投影的现有窗口管理；取消且无快照的尝试也随 bundle 过期清理。落盘异常记录 `output_retention.status=failed` 和异常类型，不截断后备链、不覆盖取消结果。

本轮不启动正式 Worker，不调用真实报告适配器，不修改运行库。真实环境验收与前端规格可在离线实现收尾后接续。

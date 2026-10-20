# 票03 两轴审查

## Standards

Standards：未发现明确的仓库规则硬违规；有 1 项非阻断建议。

- **P3，可能的 Duplicated Code（启发式）**：[认证判定](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/core_input_requirements.py:133)与[认证血缘输出](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/core_input_requirements.py:175)重复筛选“绑定该指标且 `certified_from <= period`”的认证包。依据你提供的 Fowler 基线，建议计算一次覆盖包列表，两处复用。未来修改可能导致判定与血缘不一致属于推断，当前未发现两者结果不一致。

静态追踪确认：按正式消费日 PUBLIC cutoff 选值，默认形成每结果 140 条、整窗 259 条及窗前 139 条；认证覆盖、质量和实际采用原件均受检查，血缘按 claim 保存，初始化单独标记未评估。未知／未来版本被可见性过滤；已选最新原件损坏会报缺口，未见退旧重选。对应 CONTEXT 与 ADR-0006／0018／0019；公式未改。以上为读码结论，未经运行验证。

两树均停在指定基线；三个归属文件及 01 前置文件哈希匹配，按指定顺序拼接与冻结 diff 逐字节一致。SHA-256：

- input：`2396d64fac751ceec780948aacd09167906796049c384e7a758ed76735a52243`
- diff：`ea568e614c1d75b487c9308d1469d05db68ecf083e6932bf91fd7346b5dfa69e`

未委派、改文件、运行测试、联网或读取凭据。安装及测试日志由主代理独立核验；排队重型不计通过。

## Spec

Spec 审查发现 **2项缺口，均为静态推断，未运行测试**。

1. **P2：预热日历中间缺日可被更早日期补足。** [core_input_requirements.py:20](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/core_input_requirements.py:20)直接按日历列表切取140条，仅检查条数。若日历漏掉2025-09-05、增加08-28，且认证覆盖更早历史，遗漏同日价格仍可能得到 `available`；上游解析未验证日历连续覆盖。违反[03票AC1、AC5](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/03-core-formula-warmup.md:26)固定259日及“中间断档不能被最早日期或总行数掩盖”的要求。

2. **P2：缺口原因不足以定位补证工作。** [core_input_requirements.py:122](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/core_input_requirements.py:122)将数值缺失、公开时间未知/未来、未认证和质量失败统一报为 `core_history_input_missing`；不可见版本还丢失对应claim定位。虽能阻断，却未实现[父spec实施决定9](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/spec.md:88)要求的“区分数值、发布证据、原件完整性、来源身份、字段/单位”等精确缺口。

核验：两树HEAD均为指定基线，无新commit；三文件及01前置哈希匹配，指定顺序拼接diff逐字节一致（`ea568e61…`）；输入清单SHA256为 `2396d64f…`。未混入继承变化。

边界：本增量只修改预检；[实际回放:441](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/model_evaluation.py:441)仍逐历史日检查完整前缀，不能据此宣称回放消费规则已修改。未发现越界改公式；真实来源认证不属于本票必交付。重型仍待终态，104文件及36+15日志留主代理独立核验。

Standards 1项P3启发式建议；Spec 2项P2。主代理另实际执行重型，5 failed/28 passed/73.68秒，身份未变，见heavy-03-preflight-r1；不能记票完成。

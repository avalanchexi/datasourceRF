Spec 审查发现 **2项缺口，均为静态推断，未运行测试**。

1. **P2：预热日历中间缺日可被更早日期补足。** [core_input_requirements.py:20](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/core_input_requirements.py:20)直接按日历列表切取140条，仅检查条数。若日历漏掉2025-09-05、增加08-28，且认证覆盖更早历史，遗漏同日价格仍可能得到 `available`；上游解析未验证日历连续覆盖。违反[03票AC1、AC5](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/03-core-formula-warmup.md:26)固定259日及“中间断档不能被最早日期或总行数掩盖”的要求。

2. **P2：缺口原因不足以定位补证工作。** [core_input_requirements.py:122](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/core_input_requirements.py:122)将数值缺失、公开时间未知/未来、未认证和质量失败统一报为 `core_history_input_missing`；不可见版本还丢失对应claim定位。虽能阻断，却未实现[父spec实施决定9](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/spec.md:88)要求的“区分数值、发布证据、原件完整性、来源身份、字段/单位”等精确缺口。

核验：两树HEAD均为指定基线，无新commit；三文件及01前置哈希匹配，指定顺序拼接diff逐字节一致（`ea568e61…`）；输入清单SHA256为 `2396d64f…`。未混入继承变化。

边界：本增量只修改预检；[实际回放:441](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/model_evaluation.py:441)仍逐历史日检查完整前缀，不能据此宣称回放消费规则已修改。未发现越界改公式；真实来源认证不属于本票必交付。重型仍待终态，104文件及36+15日志留主代理独立核验。
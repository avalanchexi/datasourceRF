Spec：**前轮两项预检问题已修，未发现本轮新增阻断缺陷；回放集成仍未闭合。** 以下行为判断均为静态推断。

- **新增／已修日历完整性**：依父规格实施决定2、14及03 AC5，[calendar_coverage:292](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/source_adapters.py:292)逐自然日检查未过滤原件，绑定请求范围、获取ID和哈希；[预检:531](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/material_preflight.py:531)保留`history_dates`，覆盖未证明则禁止生成正式输入，不能漏行补早日凑140。

- **已修诊断与血缘**：依[父规格决定3、4、6、9](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/spec.md:82)，[核心需求:14](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/core_input_requirements.py:14)从冻结规则派生140／259／139，而非硬编码日期；[选值:130](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/core_input_requirements.py:130)按正式消费cutoff检查认证、质量和原件。不可见候选仅供诊断，后来可见才可采用；坏最新不会退选旧版。失效原件仍可定位。初始化独立，趋势未改；[旧回执读取:82](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/material_preflight.py:82)按内容哈希读取，不随新材料重算。核心“合法旧版＋已可见坏新版”组合未见直接专例，拒收结论仅来自读码。

- **仍缺：回放消费一致性**。父规格决定6、18及ADR-0019要求正式消费cutoff；[model_evaluation:441](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/model_evaluation.py:441)仍从预热首日逐日验证全部前缀。例如09-05输入于04-01正式消费前公开，预检可接受，回放却可能先在09-05拒绝。这是07隔离集成、16真实回放须收口的依赖，不因文件未改本身判错。

- **保留缺口**：父规格US35／决定21尚未完全满足：r1恢复318件，仍缺54路径；不能称全部恢复，也不否定当前r2验证。

首尾核验一致：固定HEAD无新提交，5文件及01七文件继承基线匹配；有序diff逐字节一致，SHA256 `8b5751c6…e759`。日志确认heavy **34 passed／85.80秒／exit0**，旧5失败保留；不代表全套、真实认证或回放完成。本次未委派、修改、跑测试、联网或读凭据。
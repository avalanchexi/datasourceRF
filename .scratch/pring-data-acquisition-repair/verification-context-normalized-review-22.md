# LPR消费与双点时日历增量复核

固定基点`bda795f566f60205fc443f3854a8e2eb1b13b76c`，`git log bda795f..HEAD --oneline`为空。工作树精确范围为official_lpr.py、search_evidence.py、context_projection.py、release_calendar.py、model_evaluation.py、tests/models/test_candidate_admission.py及tests/adapters/test_chinamoney_lpr.py。用户的dashboard资源不在本次复核范围。

命令：`git diff bda795f -- src/pring_cycle/official_lpr.py src/pring_cycle/search_evidence.py src/pring_cycle/context_projection.py src/pring_cycle/release_calendar.py src/pring_cycle/model_evaluation.py tests/models/test_candidate_admission.py tests/adapters/test_chinamoney_lpr.py`。

## Standards

硬规范问题0；实质气味问题0。共用LPR校验覆盖双制品、整原件重解析及选中声明经济/来源/时间字段；检索、上下文和回放共用该校验，失败诊断血缘保留。日历先按模式过滤可见事件，再按期次及对应时间选择修订，符合ADR0006。新增测试通过公开导入与查询验证真实采用、历史隔离及原件身份，无内部业务mock。此为静态审查，未运行测试。

## Spec

首次发现1项：日历按事件ID而非模式时间选事件，未知发布时间修订会盖过较晚有可靠发布时间的新修订。根代理以calendar-red-18复现后修复排序；复审剩余0。可见事件现按月份、模式时间及取得时间排序，稳定处理并列；PUBLIC继续排除未知时间，SYSTEM保留取得后可见性。复审读取新增四cutoff测试及calendar-green-19的22通过日志，未自行运行测试。

Standards剩余0；Spec剩余0。最后的测试类型收尾仅增加非空断言及带类型的固定时钟，Ruff与mypy另行核验。结论限当前软件增量；真实来源认证、完整模型、120交易日及报告切换均未因此通过。

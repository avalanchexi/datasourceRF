# 六指数软件切片 Standards 审查

固定起点aa945dc；精确本批增量由market-baseline-334.json和market-review-348.diff/market-review-350.diff约束，既有WIP不纳入本批。按code-review两轴并行，Standards由margin_standards_review独立只读执行，规范来源为AGENTS.md、CONTEXT.md和ADR 0006/0012/0013。

明确规范违规0。首次有三项判断性建议：共享校验器名称仍限定margin；融资/指数采集前经济字段校验重复；指数采集与原件重解析的身份/去重/标量生成重复。

350复核确认全部闭合：共享声明校验统一TuShare命名、注释和内部错误；融资与指数共用家族循环，保留各自指标、接口、解析器和错误身份；指数两入口共用_market_index_scalars。未发现整理引入明确规范问题。

Standards待处理项：0。运行、最小提交及真实来源认证不由静态审查代替。

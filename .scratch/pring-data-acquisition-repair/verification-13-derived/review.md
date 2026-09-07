## Standards

基点`9199a5bad25299c0373da5878c15a2711599f01c`，工作区应用`context_projection.py`、新认证测试及旧fixture三处。初审与追加修复复审：硬规范违例0、需处理smell0。七公式守门服从模型定义，PUBLIC未知传播，日历未自动获认证；两条新增缺依赖测试通过公开边界。审查只读、未运行测试。

## Spec

初审1项：未启用credit公式也无条件要求GDP定义，触发KeyError。根代理使用规定WSL非editable环境从公开投影入口重现两个RED（关闭公式缺GDP与启用公式缺GDP），日志`../verification-13-derived-review-red.txt`。修复先跳过未启用公式，启用公式缺依赖给出明确`context_model_metric_missing`；复审0项，未降低验收。

根代理最终针对测试57通过、28.97秒，见`../verification-13-derived-review-green.txt`。初审者曾在Windows内存环境做诊断，此运行不作为项目有效验收；主代理已纠正执行边界，复审均静态，正式RED/GREEN均为WSL规定环境。

汇总：Standards剩余0；Spec剩余0（初审1项已修）。结论只覆盖派生可用性代码增量，不能代替票13官方认证矩阵及完整项目验收。

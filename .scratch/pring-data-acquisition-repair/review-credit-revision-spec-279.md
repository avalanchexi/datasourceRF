范围：269→278测试差异，基线hash匹配；未跑测试。

P2：测试6026把SourceClaimVintage当含available_at的声明视图；evidence.py:228–235无该字段。279实际2失败/85.47秒，未进入修订断言，属准备错误。应从公开metric_series(...).claims读取完整时间字段，勿扩生产类型迁就测试。

P2：6091–6097仅检查新行值/父项及旧trace，未验证新持久trace、新旧derived身份与实际模型采用集合。按issue19:30–31、spec:163，补读新trace核值/父项，断言新ID、模型采用新父项且排除被替代ID；否则行已更新但模型/trace仍旧也能通过。

未见范围越界；微秒边界区分PUBLIC与SYSTEM，历史目标日单独保留旧值；合成修订未冒充认证。未知PUBLIC与完整回放不列本次遗漏。

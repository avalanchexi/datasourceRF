# 历史来源收据修复双轴审查

基点a569fd757c7d19a4ae95b980bd2b1c0c51cba973，审当前工作区acquisition.py、source_history.py、
新增公开测试与两个原件fixture/属性。dashboard等其他改动不属于此范围。
两个独立代理按code-review并行，只读源码和字节，未运行应用。

Standards初审0；Spec初审4：自动重定向、browser原包装未保存、独立请求目标日缺失、HTTPError无读取上限。
根代理分别补公开反例；浏览器测试首次选了尚未调度的期次，已改为首个GDP期次独立复现，初稿日志保留。

Spec复审0，四项全部关闭：禁止重定向、目标日入参数、原包装先capture、错误体可选限额。
成功浏览器导入通过normalized.artifact_hash追溯解码HTML，错误包装保留原始raw；其他采集默认行为未变。
Standards最终复审0（硬违反0、smell0）：每线程owner传递、原件与时钟边界及公开测试符合规范。
GDP原件322515字节及指定SHA独立一致；社融25006字节来自旧审计原件。

未宣称PUBLIC、历史覆盖、来源认证或模型采用通过。

# 新目录 DR007 / Shibor 采集消费

2026-09-08；基线 `0452aca`。本批继续票13/19已确认的公开采集、证据查询、选值及投影测试入口。未修改旧v3认证标签、历史公开时间或生产模型。

输入为[剩余P1来源研究](remaining-p1-source-consumers.md)：根代理已校验32项输入指纹、64处本地链接；报告SHA256为`b29d4daf67fe06d1ddce2d21c38339152bdfff89f4e27f90bd09bb22d1fdf251`。这些是修改前源码快照，后续实现改变源码不回写该研究指纹。

第一切片从 `TushareContextAdapter.acquire_scalars` 调用实际 `transmission`，仅替换外部transport与时钟。TuShare响应明确为合成；数值来自已核CFETS目标日原件，不能将其当成实际TuShare历史交付收据或真实PUBLIC证据。

- `verification-interbank-red-01.txt`：1失败/5.02秒，测试transport返回dict而真实采集要求原响应bytes；先修测试形状。
- `verification-interbank-red-02.txt`：1失败/3.92秒，真实入口复现`unknown_metric_definition_version`。
- 修复 `ingest_context_scalars` 的目录解析，传入数据库路径。
- `verification-interbank-red-03.txt`：1失败/4.15秒，继而复现`registered_source_contract_not_implemented:CN_DR007`。
- 实施两项精确来源守卫：TuShare provider、DR007无维度/Shibor三个期限、percent、business_day、start=end，结构字段绑定v3基线但不继承其认证授权。

第一切片GREEN：1通过/3.94秒；扩展两PUBLIC分支后2通过/6.11秒；加来源身份边界后7通过/25.99秒。

复审共3个不同问题：日期仅比较相等而未验证日历；公开标量导入未绑定API/字段；未知PUBLIC测试主动清空原始输出，可能掩盖回归。两轴分别提出2项（日期重复），均已修复。

- `verification-interbank-review-red-01.txt`：5失败/10.38秒。非法日历日期及3API/字段错配原先未拒绝；非规范日期原先已被其他家族月解析拒绝，但缺少明确银行间期次错误。
- 现按真实、规范ISO日期校验同日；标量批量写入前绑定DR007 `repo_daily/weight` 与Shibor `on/1w/3m` 的准确期限。最后一条错配也不能部分写入。
- 未知PUBLIC测试直接保留并断言实际parser输出；仅可靠时间正例注入明确的合成时间。
- `verification-interbank-review-green-01.txt`：12通过/40.94秒；双轴静态复审剩余问题均0；mypy检查85文件通过。

关联回归完成：`verification-interbank-related-01.txt`，156通过/0失败/244.16秒；84个安装源码与工作树一致，Ruff通过。见[检查点](verification-interbank/checkpoint.json)。本批真实认证、完整真实候选、搜索配对实测、AI合格报告、切换均为0；上一批全量855通过/1次超时及单例复测通过记录继续保留，最终全量门仍未通过。

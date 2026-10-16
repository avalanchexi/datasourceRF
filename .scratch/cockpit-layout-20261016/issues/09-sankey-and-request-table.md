# 09: 桑基图与请求表

**What to build:** 读者在数据链路页看到清晰的桑基图：来源 → 环节 → 结果三列分色，连线按结果四色（成功绿、候选琥珀、未找到 / 未完成灰、失败红）、明暗主题都清晰；节点标签中文并带请求数，小来源合并为"其他（N）"，悬停看数与占比；请求表限高滚动、指标列写中文名。见 [规格](../spec.md) 用户故事 69–75，实现决定"桑基图""数据链路请求表"。

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] 节点标签 = 中文名 · 请求数，去掉"来源:"等前缀；来源名用票 02 显示名
- [ ] 结果中文与四色归类集中一处：绿 accepted / verified / validated；琥珀 candidate_source；灰 not_found / started / reserved / unknown_completion / completed；红 failed / interrupted / timeout / error / rejected；未映射值显示原值、归灰
- [ ] 节点按列分色；连线半透明、颜色取主题变量；高约 420px；请求数 <2 的来源合并"其他（N）"；悬停显示请求数与占比
- [ ] 请求表限高约 480px 内滚；指标列显示名
- [ ] 数据链路页渲染入口测试：中文标签与计数、"其他（N）"合并、四色归类、未映射值；既有数据链路 HTTP 轮询用例通过；两项必跑冒烟通过

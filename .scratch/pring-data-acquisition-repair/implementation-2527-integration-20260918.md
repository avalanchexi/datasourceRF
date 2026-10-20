# #25/#27 已验证整合基线

独立工作树 `/mnt/d/cursor/datasourceRF-integrated-20260918`、分支 `codex/integrated-acquisition-20260918`，合并提交 **cc819496042f8bc3838ea6809eb47fc90af357e9**，父版本 fd330c2（ECB与SYSTEM规则）和0946735（官方回退）。自动合并无文本冲突，三处重叠代码 context_projection/source_contract_review/worker 经两轴限定复审，无新增硬问题或建议；两侧契约、时间过滤、ECB原件复核和官方逐指标scope均保留。

新独立离线安装包 **425 passed in 305.58s，exit=0**；100源/安装文件、28选定测试文件及113全部测试输入始终不变。见 verification-2527-integrated-installed-final-20260918.json，日志sha f9f611493a620340b30ec77247e65efdd35bfd3a3ba43d0ee4f6b9c65bc0aa7c。Ruff及Mypy（三重叠源码）通过。完整diff whitespace检查发现归档官方HTML本身含空白；原件按哈希保留，排除这些原件后源码/测试diff检查干净，不改原件。独立树额外复制271既有未跟踪归档输入，逐文件哈希相同，未覆盖原件，verification-2527-integrated-fixtures-20260918.json记录。

该验证只证明整合后的相关软件回归，不覆盖新候选完整Worker发布生命周期或真实来源认证。下一步新M1/SF调用接线以公开刷新入口反例落地，再执行整合后完整Worker验收。为避免同一缺陷重复构造约35分钟生命周期材料，先在已获准的公开获取阶段复现调用契约；完整Worker仍是独立必做终验，不会用此阶段证明替代。MAIN原17项WIP保持，两个原实现分支也保留，未合并MAIN或推送/激活/切换。

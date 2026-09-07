# 13续：库存近似的报告期一致性

Execution: completed-code-batch

本批基点为 `b8d53a162efdd76ac70745e00f7a80d11c7565a8`，依据[票13](issues/13-remaining-p1-evidence.md)的“同期多维输入”和[已保存边界](inventory-period-repair-boundary.md)。修复前，6月PPI与7月名义库存、7月PPI与6月名义库存均输出可用近似。公开接口隔离反例为名义105、PPI同比5%；只有同期才应得到100。

## 已实施

`build_context_projection`的库存近似在计算及持久化前检查两个报告期。错期返回 `value=null`、`status=period_mismatch`，保留各自期次和声明身份，不生成派生身份，不自动回溯到更旧的月份。缺件、关闭公式和认证检查沿用既有边界。公式及“非官方统计的近似”标签不变。Dashboard显示“输入报告期不一致”。

公开测试使用真实 `EvidenceRepository` 及读取投影接口，只在隔离库建立fixture声明；覆盖同期及两个错期方向，并检查错期来源仍可追溯。未创建候选模型或来源认证，未写入生产库。未修改其他任务的dashboard.css/dashboard.js。

## 验证记录

- 规定WSL非editable环境，应用修改前[公开RED](verification-13-inventory-period-public-red.txt)：2失败、1通过，0.96秒。
- 安装本批源码并等待uv完成后，[针对测试](verification-13-inventory-period-green.txt)：60通过，18.88秒，包含新测试、原上下文及模型认证回归。
- Ruff通过；mypy检查82个文件通过；3个变更代码/测试文件格式检查通过。
- [两轴静态审查](verification-13-inventory-period/review.md)：Spec 0、Standards 0。
- 全套 **680通过、0失败、795.31秒**，一次全套运行，退出码0；[完整日志](verification-13-inventory-period-pytest-20260907-a.txt)、[最终收据](verification-13-inventory-period/final.json)。81文件安装指纹逐一匹配。全套期间未修改受测源码。

运行使用 Ubuntu-22.04、tywin、`/home/tywin/.local/share/pring-cycle/dev-venv/bin/python`，移除PYTHONPATH，测试库位于原生目录 `/home/tywin/.cache/pring-cycle/verification/repair-13-inventory-period-suite-20260907-a`。Windows Python仅用于独立制品字节校验，不执行应用或测试。

本批不能关闭票13整体：官方来源认证、27项候选采用矩阵、历史时间及RRR覆盖仍未齐。全项目的新目录、模型、真实检索、120日重放与切换依各自前置继续验收。

同期完成[P1认证准备清单](p1-certification-readiness.md)：根代理Windows标准库独立复核27唯一指标、68本地引用、34,721字节及SHA `0f3cb130613ee6cddbd535fff58ea11929dca2d0526ba1d2c484dbc25591f368`。18项可先整理、3项时间/用途边界、2项外补、4项派生父输入；这不是新认证矩阵。北交所[浏览器补证](margin-bse-browser-followup.md)有界调用超时，未取得有效样本；根代理交付校验通过。

下一批[P2来源时间元数据](p2-source-timing-boundary.md)已有2个真实公开RED；其draft位于.scratch，未计入本批默认测试。三次测试设置错误与最终真实缺陷分开保留，不当作新增产品故障。

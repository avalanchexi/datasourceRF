Status: ready-for-agent
Execution: M1 software slice completed
Type: implementation
Date: 2026-09-13
Scope: 14的M1；EIA API与HTML命令的登记目录采集

# EIA登记目录公开采集修复

依据[现有规格](spec.md)、[任务14](issues/14-p2-availability.md)及[已确认规划](worker-eia-planning-interview-20260912.md)实施两条独立采集入口。Worker组合行为归17，市场P1合同、真实来源认证和最终同版本项目验收仍按既定依赖完成。

## 基线与边界

- 当前分支main，起点为99c495a217b66d4bca9d6ceae4688ee69d4382bb；工作区已有其他未提交修复，不能用HEAD整体差异冒充本批变更。
- [301基线](eia-catalog-baseline-301.json)核对此前298的320项输入及4个保护文件，并保存本批三个目标文件的精确起点。两个EIA生产文件在开始时与HEAD一致；候选测试文件含已有改动，本批增量单独辨认。
- 沿用公开候选准入、EIA公开采集/HTML命令和公开证据查询。完整61项候选来自已有合成准入准备，未删除P1、替换认证守卫或激活真实模型。
- 当前会话不能无密码提权挂载旧测试卷，改用独立WSL原生ext4目录。原环境不动，53项依赖与265一致；见[环境记录301](verification-eia-environment-301.json)。后续生产修复通过离线构建wheel、仅重装项目包进入该隔离环境。
- 仍使用现有pytest和mypy入口。[验证包装301](run-eia-catalog-check-301.py)为每次调用保存精确命令、冻结输入、原生安装源码、依赖及SQLite身份的前后核验、日志指纹和实际退出码；它不提供新的生产测试接口。

## RED、根因与最小修复

| 批次 | 公开行为 | 实际结果 |
|---|---|---|
| [302](verification-eia-api-red-302.json) | 合法候选准入后API采集两种油价并读回证据 | 1失败/4.97秒；真实调用链进入EIA入库，在目录查询处抛unknown_metric_definition_version |
| [303](verification-eia-api-green-303.json) | 相同API用例，补入当前数据库路径 | 1通过/4.43秒；两种数值、单位、原件、收据、未知PUBLIC及候选状态均核验 |
| [304](verification-eia-html-red-304.json) | 合法候选下执行HTML刷新命令 | 1失败/3.39秒；刷新前查询目录抛同名错误，由CLI转为退出码2 |
| [305](verification-eia-html-green-305.json) | 相同HTML命令用例，补入当前数据库路径 | 1通过/4.51秒；1个实值与4个缺值格、单位、原件、收据和未知PUBLIC均核验 |

两处均缺少目录查询所需的数据库上下文。修复只将调用已有的数据库路径传入，不改变目录注册规则、异常捕获范围、解析逻辑或认证状态。API错误发生在响应获取后，HTML错误发生在获取前；不能将两者都表述为所有原件已丢失。

两份RED都具有实际失败栈并通过前后环境核验。测试期望是用户可读结果，不是期待抛出KeyError；只有修复对应调用才能继续完成证据断言。每次先有一个公开RED、根因和最小修复，再开始下一入口。

## 验证与交接

最终[312相关回归](verification-eia-related-312.json)实际退出0，74项通过、197.54秒，覆盖EIA adapter、HTML acquisition、context acquisition receipts三个完整测试文件及新增7个登记目录场景。运行前后320项冻结输入、4个保护文件、91个安装Python源文件、95个安装包文件、53项依赖及Python/SQLite身份一致。该结果绑定完整工作区输入；不是只含本次提交的干净HEAD全项目验收，也不与其他批次数量相加。

| 批次 | 验证范围 | 结果 |
|---|---|---|
| [307](verification-eia-api-failures-307.json) | API缺凭据、源失败、错误JSON | 3通过/7.90秒 |
| [308](verification-eia-html-failures-308.json) | HTML失败测试初版 | 1失败、1通过/6.13秒；测试错误假定源OSError会被CLI转换成SystemExit |
| [309](verification-eia-html-failures-309.json) | 按现有CLI契约纠正测试期望 | 2通过/5.62秒；未因此修改生产异常处理 |
| [310](verification-eia-typecheck-310.json) | 全部生产包及候选准入测试文件 | mypy 92文件通过 |
| [311 lint](verification-eia-lint-311.json) / [format](verification-eia-format-311.json) | 两个修改生产文件及候选测试 | Ruff通过，3文件格式通过 |
| [312](verification-eia-related-312.json) | 三份相关完整测试文件及全部新增场景 | 74通过/197.54秒；退出0 |

[Standards审查](verification-eia-standards-313.md)与[Spec审查](verification-eia-spec-313.md)均无待修项。审查固定于301工作区基线至310增量，避免将既有未提交工作计入本批。新增用例以相同公开候选准入准备、原始响应和公开查询断言为后续组合测试提供输入，不引入新测试专用生产接口。

## 向17交付的场景

场景定义在候选准入测试文件末尾四个`test_registered_catalog_eia_*`公开测试中，精确增量另存[310测试块](eia-catalog-tests-addition-310.py.txt)。组合测试应复用这些输入与期望，通过自己的合法隔离active模型生命周期进入Worker，不能用私有注册、裁剪P1或候选状态冒充生效模型。

| 场景 | 已证明的采集结果 | 17需要追加的组合证明 |
|---|---|---|
| API合法两油价响应 | validated收据、原件和两条待认证声明；未知PUBLIC不可见 | 配置EIA密钥的完整运行可继续至检索与投影；另证明采用资格 |
| API缺凭据 | 构造阶段ValueError；未发请求、无收据、无声明 | 未配置EIA时跳过可选分支；TuShare缺陷B测试不被EIA提前失败污染 |
| API源OSError | failed收据、无已收原件、无声明 | Worker按source_failed分类留证并继续后续阶段 |
| API错误JSON | failed收据、已收原件保留、无标准化/声明 | Worker按validation_failed分类留证并继续；不能只断言笼统KeyError字符串 |
| HTML合法原件 | validated收据、1个实值与4个缺值格、真实获取时点 | HTML命令独立通过不能替代Worker API组合验证 |
| HTML源OSError/无效页面 | failed收据及对应source_failed/validation_failed尝试；前者无原件，后者保留已收原件 | 保持入口差异；不把HTML已有分类当作API已证明Worker分类 |

必要软件修改尚未全部收口，项目最终默认全套仍按规格M5统一执行，不用本批专项替代。最后一次默认全套仍为183批；后续最终版本还须包含已知Worker/P1必要修改，再执行默认套件及指定共享搜索预算原失败用例。

环境准备中首次Ruff启动未找到命令二进制，随后复制同版本现有二进制恢复；该准备错误发生在运行测试之前，不计为产品RED。期间没有下载新依赖、读取实际API凭据或调用外部数据源。

任务14整体来源和日历条件、任务17组合运行、真实完整候选、120日回放、真实检索与产品交付均保持开放。下一步按M2推进P1家族注册合同与输入，再以M3合法隔离模型完成M4 Worker链路；票23继续延期。

根核验见[313限定范围验收](verification-eia-acceptance-313.json)。首次根核脚本误要求旧收据具备310才增加的包装前后字段，按收据实际版本纠正并保留[准备失败记录](verification-eia-acceptance-preparation-313.txt)，不补造历史字段或计为产品RED。本批提交仅收录两处EIA修复、新增四个测试函数及独立实施证据；任务14勾选和执行入口在原有未提交规划文档上更新，保留其余未提交工作，不将历史工作整体纳入提交。

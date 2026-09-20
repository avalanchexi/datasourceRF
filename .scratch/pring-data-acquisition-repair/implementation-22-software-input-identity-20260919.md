# #22 软件收尾：软件输入清单接入实际驱动（2026-09-19）

范围：把[已确认的提效规则](remaining-work-efficiency-20260918.md#2026-09-19确认真实采集复用软件验收)里“输入分开管理”落到实际验证驱动，使收据分别绑定软件身份与材料身份。沿用既有 `tools/check.py quick` 入口，pytest 默认完整发现不变。本切片不重新拆票，不新增性能项目。

## 先核实的环境事实

- **归档未移走必需材料**：`material_identity` 绑定的 `MATERIAL_INPUTS` 正是主目录缺失的五个目录加 `capacity-q1-source-mapping-decision.md`；它们在整合树全部在位（core-transport-196 6 件、evidence-lpr-import-20260908 19 件、evidence-a18-import-20260909 521 件、evidence-official-consumer-edge 6 件、evidence-search-preexperiment-20260908-n4-v1 51 件）。因此受影响验收须在整合树执行；主目录缺件的实际失败表现仍未实测。
- **解释器身份**：`dev-venv/lib/python3.12/site-packages/pring_cycle` 是**主目录**的非 editable 旧安装（`direct_url.json` 指向 `/mnt/d/cursor/datasourceRF`），缺 `material_preflight.py`、`commodity_basket.py` 等。裸跑 `dev-venv/bin/python -m pring_cycle` 加载的是该旧安装；只有 `cwd=整合树` 且 `PYTHONPATH=src:.` 才加载整合树代码。既有 driver 正是这样设置，本批驱动另加断言把 `material_preflight.__file__` 记进收据。该 editable 式绑定不替代独立安装制品验收。
- **旧重型任务终态**：v2 整窗预检监督实际退出 0、179.99 秒、`frozen_inputs_unchanged`/`runtime_contents_unchanged` 均真，结果为 `independent_calendar_unavailable`、`checked_business_dates` 只有 2026-08-28；v3 输入准备退出 0、349.52 秒、`frozen_inputs_unchanged` 真。启动本批前 `ps` 确认无重型进程在途，未重复启动、未改动冻结输入。

## 定位到的重复工作

既有驱动用整树哈希当软件收据：`verify-current-full-v7-20260919.py` 的 `inventory(folder)` 走 `folder.rglob('*')`，只排除 VCS 与缓存目录。实际后果在 v7 收据里可核：

- `source_and_test_inputs` 共 **3756 条，其中 3477 条是 `.scratch` 证据**（src 102、tests 120、tools 1、docs 48）。
- 冻结副本 `/tmp/datasourceRF-current-verify-20260919-v7/project` 共 **179M，其中 163M 是 `.scratch`**（src 1.9M、tests 12M、tools 8K）。
- 整合树整树清单实测 4026 文件 / **12.54–13.76 秒**；软件清单 229 文件 / **1.06–1.30 秒**（同机两次重复取值）。

两个代价分开说：一是每次清单与冻结复制都处理不影响行为的证据；二是运行之后写进 `.scratch` 的笔记会改变整树清单，使同一版软件的收据看起来失配，从而把可复用的结果推成重跑。后者才是“减少重复工作”的主要来源；前者是次要的常数开销。

## 改动

`tools/inputs.py`（整合树新增）只钉软件一半：`src/`、`tests/`、`tools/` 三棵树，加构建声明的 `pyproject.toml`、`uv.lock`、`.python-version`，以及 **从 pyproject 读出的 readme**（当前为 `README.md`，表形式读 `file` 键）。`__pycache__` 及三种工具缓存在树内出现，不是输入。材料一半仍由 `material_identity` 按构建器与内容绑定。`.scratch/` 同时承载材料与输出，所以既不整体排除也不整体计入：笔记与日志不使软件收据失效，被读取的原件仍绑定材料身份，材料变了由材料收据失配。

`tests/maintenance/test_verification_inputs.py` 先 RED：5 failed / 0.18 秒（`ModuleNotFoundError: No module named 'tools.inputs'`，退出 1），原始日志 `verification-22-software-inputs-red-20260919.txt`。实现后 5 passed / 1.30 秒（`verification-22-software-inputs-green-20260919.txt`），覆盖：运行后写入的证据笔记不改变软件收据、改一个 `src` 文件精确使该条失配、构建声明的 readme 被钉住且改动可见、树内缓存不入清单、以及本仓库实际清单只含软件三树与声明文件、不含 `.scratch`。两次都经既有 `python tools/check.py quick <file>` 入口，未改 pytest 默认发现，未改 `HEAVY_FILES`。

`docs/agents/testing.md` 增“收据绑定：软件身份与材料身份分开”一节，列出两份身份各自的范围、`.scratch` 不能整体排除也不能整体计入的理由、以及上述实测对照。`AGENTS.md` 既有入口（第 17 行）已指向该指南，未改。

## 接入实际驱动

`verification-19-preflight-complete-inputs-driver-20260919-v3.py` 是本次真正使用清单的驱动，不是单独的哈希基准。它在启动 CLI 前分别取两份身份：材料身份须等于准备阶段记录的 `verification-19-preflight-input-identity-20260919-v3.json`；软件身份由 `tools.inputs.inventory(project)` 取得并断言其中没有 `.scratch` 条目。运行后两份身份各校验一次，分别记为 `frozen_inputs_unchanged` 与 `software_inputs_unchanged`，连同 `runtime_contents_unchanged` 一起决定退出码。收据另记 `imported_from` 与 `software_inventory_seconds`。

实际终态：监督 2429970、CLI 2430265，`state=finished`、`exit_code=-15`、`reason=preflight_time_limit`、`elapsed_seconds=1830.3037737910054`；`frozen_inputs_unchanged=true`、`software_inputs_unchanged=true`、`runtime_contents_unchanged=true`、`changed_runtime_files=[]`，末次 C 盘 14.16GiB。`imported_from` 为整合树 `src/pring_cycle/material_preflight.py`，`software_inputs` 231 条、取用 1.2098 秒。结果文件 0 字节。

这是 30 分钟观察上限触发的主动中止，**不是**产品断言失败，也不是预检结论；没有 gaps 结果可引用。本次证明的是身份绑定与校验按设计工作，不证明整窗预检可在该上限内完成。该次 SIGTERM 的代价是 30 分钟且没有任何阶段证据——结果文件空、子进程无进度输出，无法说出它停在哪一天。这正是[提效计划第 3 条](remaining-work-efficiency-20260918.md#下一次继续implement的顺序)点名的“子进程无阶段输出”，下一步按根因定位处理，不加超时、不重跑转绿。

## 收益如实说明

本切片可证的收益有两项：软件清单从 4026 文件 / 12.54–13.76 秒降到 231 文件 / 1.2098 秒（驱动内实测），以及运行后写入的证据笔记不再使软件收据失配——后者消除的是“同一版软件被迫重跑”的重复工作，但本批没有发生过这种重跑，所以省下的时间无实测值，不折算倍数。冻结副本 163M 证据的复制成本尚未改动 v7 那条复制路径，属未兑现项。整套或业务耗时未测，不作提速声明。

## 质量门与范围

Ruff check、`ruff format`（两文件按仓库风格重排后通过）、`mypy tools/inputs.py`（`PYTHONPATH=src`；带 `.` 时 mypy 会把同一文件同时当 `inputs` 与 `tools.inputs`，这是调用方式问题不是类型问题）、`mypy tests/maintenance/test_verification_inputs.py` 与 `git diff --check` 全部通过。格式化后相关回归重跑 `tests/maintenance/` 两文件共 10 passed / 1.38 秒（`verification-22-software-inputs-related-20260919.txt`）。默认完整发现仍为 `python tools/check.py full --collect-only` 1882 项、4.30 秒收集、退出 0（`verification-22-software-inputs-collection-20260919.txt`）。

本切片不改产品源码：`tools/inputs.py` 与新测试是验证工具与测试，`docs/agents/testing.md` 是文档。因此未触发重型验收，也未新增完整生命周期用例，`tools/check.py` 的 `HEAVY_FILES` 不变。最终同版本必需验证仍待 #22 收尾统一完成，本记录不代替它。

## 由本批证据定位到的下一项

整窗预检 30 分钟上限中止后的有界归因见[整窗成本诊断](diagnosis-19-preflight-window-cost-20260919.md)：单日 `select` 占 108.02/123.73 秒，其中 `CN_COMMODITY_EX_HOG_BASKET` 53.99 秒与 `CN_COMMODITY_SLEEVE_CONTRIBUTION` 53.33 秒，因为族校验每次调用都把整批商品原件重读并比对指纹，而整轮材料不变。这是 #19 下一步按根因修复的对象，本切片未实施。

收尾修正一处：`declared_files` 原先用 `Path.read_text()` 再 `tomllib.loads`，会按当前 locale 解码；TOML 规定为 UTF-8，改为二进制打开后 `tomllib.load`。Ruff、格式、mypy 通过，新测试重跑 5 passed / 1.10 秒。该修正发生在 v3 整窗驱动那次运行之后，不影响那次已记录的收据。

## /code-review 后的修正

切片收尾的 code-review 提出 7 项，全部成立并已就地修复，不留待后续：

1. **软件收据没有绑定实际导入的发行物**（本环境正是风险现场：dev-venv 的 `pring_cycle` 是主目录旧构建，缺约 20 个模块）。新增 `imported_package()` 记录解析到的包目录及逐文件哈希；驱动改为向**子进程自身**取这份身份，而不是相信驱动的路径设置，并断言其中含 `material_preflight.py`。实测子进程解析到整合树 `src/pring_cycle`、103 文件。文档同步说明源码树不能替代这份身份。
2. **缺件被当成完整空收据**：`inventory(Path("/wrong/root"))` 原先返回 `{}`，驱动的前后比较会变成 `{} == {}` 并记 `software_inputs_unchanged=true`。现在三棵树或任一构建声明文件缺失即抛 `FileNotFoundError` 并列出缺什么。已核对主目录、整合树、v7 冻结副本三处声明文件均齐全，该严格化不会误伤既有树。
3. **磁盘探针失败会杀掉健康的重型运行**：`free_gib()` 原先 `check=True` 且异常被 `except Exception` 吞成 `supervisor_error`，随后 `finally` 直接 SIGTERM 一个正常的 30 分钟运行。现在探针重试三次，仍失败则记为未知并继续，只有真实读数低于门限才中止。
4. **声明的 readme 逃出树外**：`../outside.md` 原会进收据、绝对路径会让 `relative_to` 在运行中途抛错。现在直接拒绝并说明原因。
5. **收据键用 `str()` 而非 `.as_posix()`**：Windows 上会带反斜杠，与 WSL 收据永不相等。已改用 `as_posix()`，与 `tools/check.py` 一致。
6. **删除文件的反例覆盖不到**：原断言只遍历新收据，删源文件会得到 `[]`。改为双向比较并新增删除反例。
7. **文档里 229 与本批收据的 231 对不上**：229 是切片开始时的计数，新增两个文件后为 231。文档改为两值都写，并说明文件数不是判定收据过期的依据。

修复后：Ruff、格式、`mypy tools/inputs.py` 与 `mypy tests/maintenance/test_verification_inputs.py`、`git diff --check` 全通过；测试从 5 项扩到 10 项，`tests/maintenance/` 相关回归 15 passed / 1.25 秒；默认完整发现 1887 项收集、退出 0。

这些修正都在 v3 整窗驱动那次运行之后，不改写那次已记录的收据；下次用该驱动运行时收据会多出 `imported_package` 字段。

## 两轴复核（2026-09-20）：标准轴

范围为整个未提交批次（相对 HEAD `c5f0796`），比本切片更大：另含此前会话的 #19 预检 WIP（`material_preflight.py`、`test_material_preflight.py`、`cli.py`、`context_replay_scope.py`、`model_evaluation.py`、`test_isolated_lifecycle.py`）。提交时这些会一同进入，故一并审。

两条硬违规已修：

1. **`tools/check.py` 重型清单漏项**。`docs/agents/testing.md` 明文「新增完整生命周期用例时更新 `tools/check.py` 的重型文件清单」，而 `tests/models/test_material_preflight.py` 从 `test_isolated_lifecycle` 导入 `admit_complete_candidate`，确实准备完整公开模型生命周期，却不在 `HEAVY_FILES` 中——`quick` 会放行它，与该门设计意图相反。已加入清单，实测 `quick` 现正确拒绝并提示需显式重型验收。该遗漏来自此前会话的预检 WIP，不是本切片引入。
2. **新增文档段落指错模块**。「**实际导入的发行物** 由同一模块的 `imported_package()` 记录」紧接在 `test_isolated_lifecycle.py` 那条之后，会被读成指向该文件，而该函数在 `tools/inputs.py`。已改为直接点名 `tools/inputs.py`。

顺带修复 `tools/check.py` 的格式：HEAD 版本即不过 `ruff format --check`（docstring 后缺空行），提交 `9201208` 时带入，非本批引入；既已编辑该文件，一并补齐。本批 11 个文件现全部通过 ruff check 与 format。

以下判断题**采纳但延后**，理由是它们都在 `material_preflight.py` 内，改动即作废已完成的 4/4 受影响重型（约 1.6 小时），当前换取的是可读性而非正确性，留待下一个接触该文件的切片一并处理：`_gap_bucket` 归属桶表达式重复两处；上海时区 cutoff 构造重复三处；`_parent_material_diagnostics` 与 `full_retrieval.py` 的 frequency→期次标签同形，应共用一个函数；`start`/`end` 四层穿透可收成窗口类型；`destination` 宜改名 `bucket`。

**部分不认同**：`adoptable()` 返回「本期可采用的点」，形容词在该语境可读，不改。`find_formula_documents` 迁入 `context_replay_scope` 确实给该模块多加一个变更理由，但为一个纯递归遍历函数另起模块不划算，保持现状并记录该权衡。

**未决，需用户裁定**：`material`/`preflight`/`adoptable` 等新概念未进 `CONTEXT.md`。`docs/agents/domain.md` 要求术语先在 CONTEXT.md 定义，而 `remaining-work-efficiency-20260918.md` 写明本轮「不引入业务领域概念或难逆架构决定，不新增 ADR 或修改 CONTEXT.md」。两条约束冲突，且改 CONTEXT.md 属难逆决定，不擅自执行。

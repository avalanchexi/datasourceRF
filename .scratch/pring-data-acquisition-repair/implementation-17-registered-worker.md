# 票17 Worker 注册目录路径（2026-09-15起）

基线HEAD `f14683a`（票19完整隔离生命周期`8c79143`之后）。公开测试`tests/integration/test_worker_registered_catalog.py`从票19材料（`isolated_lifecycle_material`）复制已激活的合成完整候选，经公开任务提交与`process_pending_run`执行；只替换外部transport与时钟，发布已知时沿用既有`retrieval_release_resolver`注入先例。工作区含无关的仪表盘css/js改动，会改变代码哈希，因此迭代在干净HEAD检出批次`e-ticket17`中进行，材料按身份键复用或重建。长时运行脱离后台任务管理（`setsid nohup`）并以监视器守护可用内存。

## 17-1 官方定向刷新

- `worker-official-red`：首轮停在发布闸门`unknown_release_configuration`——非LPR指标需已有该期次已校验发布声明，属既定产品行为；按先例改用`retrieval_release_resolver`。
- `worker-official-red-2`：精确RED——官方原件采集为`verified_candidate`后`worker_failure:KeyError:'unknown_metric_definition_version'`，即`worker.py`官方刷新认证查询漏传`database_path`。
- 修复后`worker-official-green`（含材料重建）暴露两处测试准备错误：显式截止取提交时刻，执行时的采集不可见（诊断：同运行库截止+1小时选择完整9成员），按先例改为当前+1天；按期次挑到材料中8月LPR收据，改按`official_http_get`与来源URL挑选（官方收据原件哈希与提供文档一致）。

## 17-2 TuShare必需/可选失败

测试以六指数（P1）或GDP（P2）返回结构非法响应，其余TuShare家族网络错误，显式不配置EIA；核心用core-transport-196真实原始行。`worker-official-green-2-tushare-red`：两参数均被`worker_failure:KeyError:'unknown_metric_definition_version'`掩盖（TuShare已实际请求），即家族失败后优先级查询漏传`database_path`。修复后`worker-green-3`：官方与必需参数通过；可选参数在上下文刷新4秒完成（GDP `validation_failed`，其后美债/银行间已请求）后，于`FullRunRetrieval.retrieve`运行67分钟仍未写出缺口计划，按实施者决定终止（`verification-wip-20260914-e-ticket17-worker-green-3-interruption.json`）。

## 注册目录完整运行容量

[剖析](profile-17-full-retrieval-20260915.txt)（300秒采样）：缺口计划每个范围`ModelInputSelector.select`复核商品声明，每次新建期货读取器从基日重算整链（约11.5秒/次）。Worker任何执行路径均不写期货输入收据（唯一写入为审查输入导入`acquire_futures_inputs`），故在`process_pending_run`调用`_execute_run`处加`shared_futures_input_reads()`。[复剖析](profile-17-full-retrieval-shared-20260915.txt)300秒内完成检索并进入评价。

[完整运行测量](measure-17-full-run-20260915.log)（目标2026-08-28、无凭据）：

| 版本 | 秒 | 峰值RSS | 结果 |
|---|---:|---:|---|
| 共享读取 | 440.5 | 7718MB | completed，投影发布 |
| 选择缓存上限1024（已回退8192） | 1374.6 | 7709MB | completed |
| 商品复核按输入组逐个处理并及时释放 | 341.0 | 3328MB | completed，投影发布 |

峰值根因：商品复核单次调用把窗口内每天约12MB的派生快照及每天整链规范化结果同时保留。改为按输入身份分组、按日期顺序处理，每组载入一次快照、每天重算一次并在换日时释放；比较仍为精确对象比较，快照无效则该组声明无效。

## 配置TuShare令牌时的完整运行容量

`worker-green-4`（材料重建后）官方与必需参数通过；可选GDP参数完整运行在`refreshing_evidence`停留31分钟以上且无缺口计划（同代码无凭据341秒完成），按实施者决定终止（`verification-wip-20260914-e-ticket17-worker-green-4-interruption.json`）。py-spy因无ptrace权限不可用，改以剖析脚本在相同条件（令牌、真实核心行、GDP非法结构）复现：

- [剖析](profile-17-full-retrieval-tushare-20260915.txt)：核心刷新写入交易日历后缺口计划覆盖整个日窗口，选择次数大增；每次选择的广度复核重读全部审查证明文件（300秒内446万次读），300秒864次选择。
- 新增`read_scope.py`通用“一次一致读取”范围：期货读取器改基于它（`shared_futures_input_reads`接口不变）；广度复核在范围内缓存。[复剖析](profile-17-full-retrieval-tushare-scope-20260915.txt)300秒2287次选择，仍在计划阶段。
- 声明级范围缓存：同一范围内，商品复核按`(数据库, 目录版本, 模式, 截止时刻, 声明ID)`、广度复核按`(制品目录, 目录版本, 声明ID)`记录结论，未命中的声明才读取父原件复核；范围外行为不变。[完整剖析](profile-17-full-retrieval-tushare-claims-20260915.txt)：**476.6秒跑完**，采样峰值3294MB。

## 17-3 EIA四场景完整运行

`test_worker_full_run_publishes_the_registered_projection_across_eia_conditions`参数化缺凭据/成功/网络失败/解析失败，经`submit_manual_full`到`process_pending_run`，核对运行完成、投影模型与目标日、EIA两行采集状态（`missing_credentials`/`verified_candidate`/`source_failed`/`validation_failed`）、渠道`eia_official_candidate`、登记目录版本、`awaiting_source_certification`与仅背景角色，成功场景读回Brent 71.25，采用记录指向同一投影。

- `worker-eia-1`：WSL虚拟机重启导致pytest临时目录I/O错误，记为环境中断（`-io-error`）。
- `worker-eia-2`：缺凭据、成功两场景通过后虚拟机再次重启（`Bus error`，守护未触发），记为环境中断（`-vm-restart`），不计为有记录通过。
- `worker-eia-3`：网络失败、解析失败2通过/425.7秒，pytest常驻约3.3GB、可用内存约4.5GB（`vitals-8.log`）。四场景将在17-5限定回归中同版本全部重跑。

## 17-4 固定目标日2026-09-11

[探针](probe-17-target-0911-20260915.log)：只把核心行情合成延伸到09-11，完整运行即completed并发布投影（315秒、峰值3.3GB），其余P1按降级处理。测试`test_worker_full_run_for_a_fixed_target_retrieves_gaps_and_failure_keeps_the_projection`以扩展核心与上下文transport（沿用材料导入器合成公式）执行目标日09-11、实际执行晚于目标日的完整运行，再以`index_daily`非法结构运行同目标。

- `worker-target-1`：测试键名错误（初始计划字段为`initial_system_as_of`）。
- `worker-target-2`：首次运行completed、截止点冻结断言与`index_daily`请求validated通过，失败于“CSI300 09-11缺口补齐”。运行库诊断：Worker补到的沪深300声明`release_at`/`public_available_at`为空（TuShare不提供发布时间，走`unresolved-publication`），非核心指标经`TargetBoundEvidenceRepository`按目标日`public_as_of`约束，未知PUBLIC时间保持未知，故P1缺口未解决且未采用——既定规则，不是缺陷；材料内历史值可用是因导入时标注了合成发布时间。同运行三项P0核心资产（SYSTEM路径）在09-11补齐、被采用，并追溯到Worker自身`index_daily`/`fut_index_daily`请求。测试预期据此改为：核心补齐与采用；CSI300请求validated但缺口未解决、未采用；广度仍为未解决P1。改后断言已在该运行库离线逐项核对成立，失败保留旧投影部分待重跑。
- `worker-target-3`：1通过/369.9秒。首次运行completed，SYSTEM在采集后冻结一次且晚于提交截止，运行、报告截止、投影与最终计划共用；P0核心在09-11补齐并采用、追溯到本运行请求；随后`index_daily`非法结构的同目标运行`action_required`（`worker_failure:ValueError:`），无新投影，当前投影仍为首次投影且数据集不变。

待业务确认的观察：实时完整运行经TuShare补到的P1日度值没有发布时间，按目标日PUBLIC规则永远不能补齐缺口。这是既定规则的结果，不是本票缺陷，但意味着实时P1补证要依赖发布时间来源（审查或日历规则）。已在17验收说明中列出，不在本票修改。

## 17-5 两轴审查（2026-09-15）

范围：HEAD `f14683a`以来票17的6个文件。

**Standards（均为判断项，无硬性违规）及处理**
- 缓存前提描述不准：Worker运行会采集其他证据，并非“什么都不采集”。已把`read_scope.py`、Worker及两处复核的注释改为精确前提：缓存结果只依赖声明自身不可变父原件，以及只由审查导入采集的期货输入。广度复核只读父原件；商品复核读父原件和该截止点的期货输入（`calculate_commodity_basket`只经期货读取器），键中含截止点。
- 重复逻辑（两处“已知/未知声明拆分、复核、回写”，且已出现分歧）：抽取`read_scope.claims_checked_once`，由两处共用。
- Worker改为直接用`shared_read_scope`；`shared_futures_input_reads`保留给已提交的调用方。
- 商品复核在重算失败时，同日其余声明会和`None`比较：改为重算成功后才记录日期，失败则重试。结论不变，但可读性更好。
- 测试：`json`移到模块顶部，非法结构响应抽成常量。从`tests.models.test_isolated_lifecycle`导入材料的做法沿用票19交接接口，保留。

**Spec 及处理**
- 定向补齐与后续实际采用分别留证：09-11用例先执行官方PPI定向刷新，再核对完整运行采用集合包含刷新得到的8月PPI声明（原件读回）。
- 模型身份与验收收据可查询：用例查询生效模型、验收收据（`acceptance_details`）和激活记录首发目标日。回放收据查询会载入630MB上下文输出文档，已随#16另列，不在Worker用例中调用。
- TuShare原异常与请求身份：失败接口的收据断言为`failed`/`ValueError`，并读回非法原件；可选GDP场景新增运行completed且发布投影的断言。
- EIA网络/解析：收据`error_type`分别为`OSError`/`ValueError`；缺凭据时不产生收据。
- 09-11失败运行：核对失败原件、`validation_failed`分类，并确认已存声明和首次运行的采用集合不变。
- 保留为说明：报告沿用截止点只核对运行记录`report_cutoff`与投影一致，用例未生成报告；修订规则不在Worker用例覆盖范围内；官方路由沿用发布日历注入先例。

## 17-5 联合验证准备（暂停中，2026-09-16）

- 17-4 `worker-target-3` 1通过/370.5秒（改后断言，含同目标必需失败保留旧投影）。
- 两轴审查修复保留（`claims_checked_once`、Worker改`shared_read_scope`、测试补强）；已核对前提：期货读取器只消费`bind_futures_input_evidence`绑定的`futures_input_evidence`批次，Worker自身`fut_daily`收据不进入读取器。
- #16已提交（4618af7/3c6ba33）；e-ticket17检出切到`3c6ba33`并叠加票17六个文件（逐一核对与工作区一致），一次材料重建同时验证#16回放/激活路径与票17 Worker用例，并采集#16切片4容量（上下文输出文档字节数、model-replay/activate峰值RSS）。
- 脚本`e-ticket17/scoped-17-5.sh`（逐个运行、`tmp_path_retention_policy=failed`、失败保留现场并停止、通过即删临时目录）与`guard-17-5.sh`（5秒采样；可用内存<1.5GB或C盘剩余<2GB即终止）。旧材料`b6ec69ab…`已删除。
- 暂停原因：C盘剩余降至约0.8～1.3GB（Windows侧占用，WSL的vhdx与swap大小未变）。待`wsl-sparse-reclaim.ps1`回收空间、C盘恢复到8GB以上后启动。

## 17-5 联合验证执行

材料重建（`scoped-official`通过，1869秒）经公开`model-accept`/`model-replay`/`model-activate`成功，新材料`8a84b451…`，同时验证#16回放与激活路径；容量见[#16记录](implementation-16-context-output-references.md)：上下文输出文档52,344,854字节（旧630,040,091为字符数口径），采样峰值RSS model-replay约577MB、model-activate约568MB，材料3.0GB（原3.5GB）。

`scoped-lifecycle`：完整构建用例通过（2273.5秒），材料复制用例失败于`isolated_lifecycle_material_contents_changed`。原因为实施者在材料目录内用SQLite直接读取该库测量#16容量，只读连接仍在旁边生成`-wal`/`-shm`，材料多出文件即判为改动；数据库自身哈希未变、`-wal`为空。删除两个旁文件后1901项内容逐项复核一致，改为只重跑复制用例。教训：材料一律先复制再读取，不在材料目录内打开数据库。

### 限定验收结果（检出3c6ba33叠加票17六个文件，同一材料`8a84b451…`）

| 记录 | 结果 | 秒 |
|---|---|---:|
| scoped-official（含材料重建） | 通过 | 1869.5 |
| scoped-lifecycle（完整构建通过、复制用例受旁文件影响失败） | 见上节，已单独重跑 | 2286.0 |
| scoped-lifecycle-copy | 通过 | 66 |
| scoped-target（固定目标日2026-09-11） | 通过 | 367.3 |
| scoped-tushare-required | 通过 | 24.8 |
| scoped-tushare-optional | 通过 | ~300 |
| scoped-eia-missing / success / network / parse | 四场景全部通过 | 各约200 |
| scoped-related（21个文件450用例） | 通过 | 1593.2 |
| scoped-mypy-packages（`mypy`，packages=pring_cycle，98源文件） | 通过 | 0.3 |
| scoped-ruff（`ruff check src` 及本票测试） | 通过 | 0.1 |

宽口径`mypy src tests/integration/test_worker_registered_catalog.py`沿导入拉入测试模块后报24错、2文件：`tests/adapters/test_commodity_basket.py`20处为票19旧有；`tests/models/test_candidate_admission.py`4处由#16（4618af7）引入，已转#16修复。本票测试文件自身无错。项目配置门槛为`packages=["pring_cycle"]`，标准命令全通过。

`scoped-lifecycle-clean`：无其他进程接触材料时整文件重跑，2通过/1789.9秒（完整构建与材料复制），确认前一次复制失败仅由实施者读取产生的sqlite旁文件引起。是否让内容校验忽略sqlite旁文件，另立事项，不进本票。

## 代码健康（票17审查遗留，2026-09-16）

- 期货读取器模块拆分：`futures_inputs.py`只保留采集、证据绑定与事实重建（1151→679行）；新增`futures_input_reads.py`（509行）承载`FuturesInputReader`、`_BatchIndex`、选择缓存、`select_futures_inputs`、`futures_input_reader`、`shared_futures_input_reads`与`_meaning`。读取侧经明确接缝读取采集侧：`input_facts`、`fact_key`、`read_artifact`、`publication_time`、`damaged_review_contract_scope`由私有改为公开命名，其余保持私有。消费方（commodity_basket、model_evaluation、适配器测试）改为从新模块导入，行为不变。
- 材料内容校验忽略sqlite旁文件：`_runtime_contents`跳过`-wal`/`-shm`/`-journal`，任何读取者都不会再造成假的`isolated_lifecycle_material_contents_changed`；新增反例`test_material_contents_ignore_sqlite_sidecars_but_not_stored_files`（未修复时失败），仍比较材料自身文件。复制材料时不跳过旁文件，未检查点的WAL内容不会丢失。
- 验证（工作区小库，未重建材料）：`tests/adapters/test_futures_inputs.py`与`test_commodity_basket.py`共91通过/95.8秒；`test_registered_commodity.py`、`test_futures_warrant_completeness.py`及生命周期非重型用例12通过/48.3秒；`ruff check src tests`通过；`mypy`（packages=pring_cycle）96源文件通过。改动使代码哈希与构建器哈希变化，现有材料`8a84b451…`失效，下次重型验证时一并重建。

上述两项与会话(2)的美债时钟修复在同一版本`1fa16c5`上做了一次[联合回归](verification-joint-20260916.md)：adapters 91、replay 86、admission 656、lifecycle 3、worker 67，共903通过/0失败，约108分钟；材料在lifecycle组内重建一次（新身份`ddeace1d…`）。worker组含注册目录8项及Worker执行、完整运行检索全部用例，确认读取器拆分后行为不变。该回归范围限于两批改动，不等同于最终同版本默认全套，票17该条件仍未关闭。

## 冻结树Standards复审的跟进（2026-09-16）

会话(2)对 `31735d6..9929b45` 做冻结树Standards复审，涉及本会话文件的三项已处理：

- 证据完整性（中）：跳过旁文件后，未检查点WAL中的已提交数据既不哈希也不校验。改为存材料前 `PRAGMA wal_checkpoint(TRUNCATE)` 并删除旁文件，复制前断言暂存目录无旁文件——材料本身不含旁文件，校验跳过的只可能是后续读取者新建的。新增反例 `test_checkpointing_folds_committed_wal_content_into_the_hashed_database`：提交后WAL非空，检查点后旁文件消失且只复制主库仍能读回该行。
- 文档漂移：`isolated_lifecycle_material` 文档串补充"数据库先检查点，清单之外只可能是读取者新建的sqlite旁文件"（docs侧由会话(2)修）。
- 接口宽度：`fact_key` 与 `damaged_review_contract_scope` 仅被读取侧使用，移入 `futures_input_reads.py`，采集侧公开面收回到 `input_facts`/`publication_time`/`read_artifact` 三项（617行 / 565行）。

验证：旁文件与检查点反例2通过/0.8秒；适配器91通过/106.2秒；`ruff check src tests` 与 `mypy src`（96源文件）通过。改动使材料失效，重型复验随下一批重建一并进行。

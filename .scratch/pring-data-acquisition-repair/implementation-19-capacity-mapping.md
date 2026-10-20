# Q1 产能映射：准入、入库与消费校验

**最新182：历史无服务标记目录兼容已完成本切片验证。** 新增单映射6例和多映射4例
共10通过、0失败/31.77秒；mypy1、Ruff、Spec182/Standards182通过。
[根核验182](verification-capacity-history-acceptance-182.json)核274输入/4保护文件、原生前后收据和辅助文件不变。
178使用152真实旧合成库；181使用157真实旧多grant库，原数据库字节和模型清单未变，
一个被原RED损坏的制品仅在新fixture按原已注册SHA从完整副本恢复，22制品全部匹配。
PUBLIC旧截止点明确选中73.6，未选73.7映射或独立依据缺失/损坏仍阻断旧目录ytd采用，
防止凭typed形状URI重解释旧状态。诊断ID及原模型身份保留。
两个fixture的40文件已确认普通暂存可见，但尚未暂存或提交。
源码本切片0变化；下方163仍是当时Q1关联结果，不能相加为新的全套通过数。
当前冻结182的默认全套183已启动，尚未终态；整票19、Worker新目录、信用脉冲整窗/修订、
真实来源认证、完整候选、120日、真实AI及切换继续开放。下方为历史分批记录。

状态：**2026-09-11已恢复；163同版本关联回归132通过、305未选/631.42秒，前验、测试、后验均0，根核验已完成。** [163根验收](verification-capacity-acceptance-163.json)绑定冻结160的230输入、4保护文件、91安装源码及53依赖；161用户中断记录保留。此后SQLite生命周期切片修改storage/worker，不能把163结果当作新代码全套验收。完整Q1历史无服务标记目录兼容仍待完成，真实认证及完整模型未通过。原Q1生产批尚未提交。

## 最新增量153–159

新增检验沿既有公开准入、入库、实际采用和组件回放入口执行。每个反例先验证合法正例；后发修订与审查为合成测试材料，不授予真实来源认证或历史首发证据。

| 记录 | 实际结果 | 分类与边界 |
|---|---|---|
| [回放153](verification-capacity-terminal-153.json) | 6 passed / 40.62秒 | 比较/候选目录，raw、normalized、mapping 缺失及损坏；限定组件回放 |
| [入库154](verification-capacity-terminal-154.json) | 16 passed / 130.07秒 | 缺/借/多收据、坏规范化、独立累计列、缺/重复/错总行等；执行器未先观察前验结束就启动测试，不能作为严格有序验收，最终关联需重验 |
| [版本155](verification-capacity-terminal-155.json) | 8 passed / 57.67秒 | 新原件不扩充原目录授权及单日回放；前验、测试、后验均0 |
| [晚期映射RED156](verification-capacity-terminal-156.json) | 1 failed / 54.48秒 | 晚期映射损坏导致早期有效累计声明也被剔除，产品缺陷 |
| [引用角色RED157](verification-capacity-terminal-157.json) | 6 failed / 40.01秒 | 上述回放反例与5种未受准入验证的类型声明；普通文件、错误引用、混合角色及自声明均可绕过预期拒绝 |
| [安装158](verification-capacity-install-158.txt) | 退出0 | 独立环境离线重装生产增量，未升级依赖 |
| [类型158](verification-capacity-mypy-158.txt) | 4项测试类型错误，退出1 | 修正可空 ID、损坏哈希变量和闭包类型；未据此更改生产行为 |
| [类型159](verification-capacity-mypy-159.txt) | 8文件通过，退出0 | 仅测试类型修正；生产仍为158 |
| [修复GREEN159](verification-capacity-terminal-159.json) | **9 passed / 136.64秒** | 晚版本 raw/normalized/mapping/独立依据失效的双日回放及5项准入角色拒绝；前验/测试/后验均0 |
| [共同依赖160](verification-capacity-terminal-160.json) | **7 passed / 54.20秒** | 请求、包、审查、history/fields普通附件、未分类映射/依据坏件，检索与实际采用拒用；前验/测试/后验均0 |
| [同版本关联161](verification-capacity-terminal-161.json) | **用户暂停中断，退出2** | 62 passed、305 deselected / 377.41秒，剩余用例未完成；前验/后验0。原执行器记录failed，结合SIGINT暂停记录分类为用户中断，不是新增产品失败 |

生产158增加经准入验证的映射引用角色，并将服务生成的解释版本绑定到不可变原始请求。旧目录及未分类的附件保持旧依赖语义；共同请求、包、审查及普通证据仍必须完整。只有明确分类的独立映射可以单独失效，所选原件对应映射的依据仍必须完整。不得回退旧窗口掩盖坏最新输入。

[Spec158](verification-capacity-spec-review-158.md)新增确定实现问题0；[Standards158](verification-capacity-standards-review-158.md)新增硬性违反及新smell均0，既有P3保留。两份报告按生产158及测试158审查，明确排除随后159的测试类型修正，不预判运行GREEN。[Spec160](verification-capacity-spec-review-160.md)与[Standards160](verification-capacity-standards-review-160.md)对七参数增量均无新阻断；160的8文件mypy、Ruff及格式通过。159、160前后各核230输入、4保护文件、91安装源码及53依赖一致。未分类引用负例来自当前服务新准入目录，不能替代无服务标记历史目录的运行兼容性验证。

161收到用户暂停指令后，验证原执行器PID530919/start_ticks1096704，再向专属测试子进程发SIGINT；真实退出2、后验0，执行器及测试子进程均已退出。根核验脚本未执行，SQLite162诊断未执行。用户继续后应核对冻结160并用新批号重新执行此关联范围，保留161原终态。首次启动161的内联Python命令因PowerShell/WSL引号传递产生SyntaxError，执行器未启动；改为stdin传递后实际启动。这是启动准备错误，不是pytest失败。不得累加不同版本结果作为整体通过数；Worker、信用脉冲整窗/修订、SQLite及真实模型最终门仍开放。

## 最新增量144–151

候选准入现在解释审查附件，逐格核对实际原件、定义哈希、单位、期间和映射目标；不是只核附件哈希。消费者显式传入目标目录，并从真实存储声明重新调用入库合同校验。三条调用路径为检索、上下文实际采用和回放资格门；诊断引用仍保留。

| 记录 | 实际结果 | 分类与边界 |
|---|---|---|
| [消费RED144](verification-capacity-selection-red-144.txt) | 1 failed / 10.06秒 | 已入库后损坏映射仍被选中，产品缺陷；同批修复后3通过14.21秒 |
| [消费145](verification-capacity-consumers-145.txt) | 4 passed / 26.08秒 | 入库/检索/实际采用、候选与比较目录的单日PUBLIC回放；不是120日验收 |
| [准入146](verification-capacity-admission-red-146.txt) | 收集失败，退出4 / 9.83秒 | 测试装饰器误放，未取得产品反例；原日志保留 |
| [准入RED147](verification-capacity-admission-red-147.txt) | 1 failed / 18.45秒 | 原格73.6、目标73.7且所有哈希自洽仍创建模型，产品缺陷 |
| [准入修复147](verification-capacity-terminal-147.json) | 5 passed、1 failed / 33.34秒 | 错映射已拒绝；CLI转换为SystemExit(2)，测试仍预期ValueError，属于断言错误；后验通过 |
| [矩阵148](verification-capacity-terminal-148.json) | 0执行，退出4 | 命令误写不存在的tests/official目录；保留原日志和终态，未改产品/用例后改正确路径 |
| [矩阵149](verification-capacity-terminal-149.json) | **30 passed、365 deselected / 120.88秒** | 16种单条件、哈希自洽的错误映射均先合法准入再验证拒绝；检索/实际采用覆盖raw、normalized、mapping损坏；输入冻结148 |
| [版本150](verification-capacity-terminal-150.json) | 1 failed / 17.79秒 | 原目录不扩权、新目录新映射入库已通过；SYSTEM历史定向任务预期complete错误。该入口既定public_as_of要求PUBLIC，未知发布时间应缺口；测试准备问题，未改产品 |
| [版本151](verification-capacity-terminal-151.json) | **1 passed / 15.06秒** | 同URL新raw不得继承旧映射，后续模型同目录不扩权，新目录独立映射可入库；无新发布时间修订的SYSTEM查询/实际采用可见，历史目标两模式均缺口；输入冻结151 |
| [统一关联152](verification-capacity-terminal-152.json) | **31 passed、365 deselected / 127.28秒** | 两个文件的 `-k capacity` 在冻结151同一版本执行，真实测试/后验退出0；仅是本切片限定验收 |

149及151均测试/后验退出0；各自核230冻结输入、4受保护文件、91安装源码、53依赖一致。151仅新增/修正测试，7个生产文件自147未变；不同测试版本结果不加总。149与151的合成review、合成修订均不构成真实来源认证或历史首发证据。默认全套最后仍为1146通过/2失败，未重跑。

[147 Spec](verification-capacity-spec-review-147.md)确定实现问题0，已识别CLI断言问题；[147 Standards](verification-capacity-standards-review-147.md)硬违反0、既有P3维护建议1，未发现当前语义分歧。[151 Spec](verification-capacity-spec-review-151.md)新增确定问题0，[151 Standards](verification-capacity-standards-review-151.md)新增硬违反/新smell均0；[mypy151](verification-capacity-mypy-151.txt)当前8文件通过，Ruff与格式8文件均通过。[152根验收](verification-capacity-acceptance-152.json)重新核230输入/4保护文件、实际终态、后验91源码/53依赖、静态检查及四份审查哈希；未将专项通过扩大为完整Q1、全套或产品完成。

以下为首段134–143历史记录，后续状态以上方为准。

新目录过去一律拒绝 Q1 的累计值。现在只有该目录原入场模型绑定的已审映射、完整定义哈希、精确原件、解析版本、源格及目标身份全部匹配，公开入库才接受同一区间的两个观测身份。原件 73.6% 对应 quarter_rate 和 ytd_rate，-0.5 百分点仍为独立同比；不把复用格当成新增官方独立字段。

实现位于 [来源合同](../../src/pring_cycle/source_contract_review.py)、[入库前校验](../../src/pring_cycle/evidence.py)、[独立 Q1 原格资格检查](../../src/pring_cycle/official_context.py)。保留 parser v0004 的原字节转换；新校验不改变旧收据、新建生效模型或正式来源认证状态。映射附件同时必须出现在 semantics 与 fields 审查证据中；资格来自目录的 admitted_by_model_id，不从最新模型借用。

## 实际验证与失败分类

| 记录 | 结果 | 分类与边界 |
|---|---|---|
| [RED134](verification-capacity-red-134.txt) | 1 failed / 5.09 秒 | `registered_capacity_q1_mapping_unresolved`，缺失的产品实现 |
| [安装139](verification-capacity-install-139.txt) | 构建依赖下载超时，退出1 | 环境安装失败，未启动测试；随后140用既有离线缓存安装成功，未升级53依赖 |
| [首轮140](verification-capacity-first-140.txt) | 1 failed、1 passed / 14.45 秒 | 新正例已入库；截止点前断言误把“无声明和选值的占位”当作数据可见。改为断言 claims、selected_claim_id、selected_value 均不可用，保留原失败 |
| [复验141](verification-capacity-first-141.txt) | 2 passed / 9.12 秒 | 精确映射正例、双点时、旧无映射拒绝通过 |
| [时钟反例142](verification-capacity-public-red-142.txt) | 1 failed / 7.65 秒 | Spec发现后真实复现：公开直接追加可提前PUBLIC，`DID NOT RAISE` |
| [修复142](verification-capacity-public-green-142.txt) | 2 passed / 10.56 秒 | 声明任一公开时钟已知时，二元组必须等于重建原件；两者未知保持未知 |
| [关联143](verification-capacity-related-143.txt) | **7 passed、365 deselected / 22.61 秒** | 两个测试文件的 `-k capacity` 范围，不能加总为项目完成率 |

最终绑定 [142输入清单](verification-capacity-inputs-142.json)，[143终态](verification-capacity-terminal-143.json)测试与后验退出码均0。后验230冻结输入、4受保护文件、91安装源码及53依赖一致；[mypy](verification-capacity-mypy-143.txt)4个指定文件通过，[Ruff](verification-capacity-ruff-143.txt)及[格式检查](verification-capacity-format-143.txt)通过。默认全套最后实际仍为1146通过/2失败，未重跑。

141测试断言修正时曾重新运行139准备脚本，覆盖其测试哈希；已由[141固定输入脚本](verification-capacity-pin-141.py)按唯一断言差异恢复140所用测试字节指纹，另存141清单。没有把新测试重新标为140输入，140原终态和失败日志保留。

## Standards

[141](verification-capacity-standards-review-141.md)及[142增量](verification-capacity-standards-review-142.md)：0项硬性违反，保留1项P3非阻断维护建议——认证JSON/CAS读取形状与既有准入代码重复。未为此扩大本切片重构。

## Spec

[141](verification-capacity-spec-review-141.md)发现1项P1：公开追加提前PUBLIC；实际RED142后修复，[142复审](verification-capacity-spec-review-142.md)原问题关闭、新增0。首段通过不替代后续矩阵。

## 继续执行

1. 当前切片静态检查、增量复审及同一输入关联已由152收口；后续修改新建冻结清单，保留本次31通过原记录。
2. 继续补入库前缺收据/借收据/坏制品、独立累计列不得套别名、缺/错/重复总行及不同vintage的公开回放反例；raw/normalized损坏的回放门尚无本批专门反例，不能由检索/卡片测试替代。旧未映射负例继续保留，当前矩阵不代表完整Q1关闭。
3. Q1完成后按依赖推进Worker目录传递/官方路由、信用脉冲25个社融及9个GDP父输入整窗校验和GDP修订兼容；SQLite继续独立定位，不因重试通过关闭。
4. 最终在同一版本完成跨模块关联、默认全套及后验，再分别进行真实来源认证、完整候选、固定120交易日双点时、真实AI报告与切换验收。

140–152测试均已有终态，当前没有本批运行中的测试或安装。真实来源认证、完整候选、120日、合格真实AI和切换均未由本批完成。

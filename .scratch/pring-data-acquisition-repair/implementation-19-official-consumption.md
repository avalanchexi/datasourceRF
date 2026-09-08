# 其余官方宏观指标消费接入

2026-09-08，在 CPI 工作树上继续票13/19。依据 [16项来源契约研究](remaining-official-consumption-contracts.md)，沿用已批准的官方导入、双点时查询、模型选择和上下文投影公开测试入口。

先以一份真实 PMI 七月原件、三个指标和八个独立审计值做纵向 RED；之后逐家族接通成员、单位、期次及必要完整性。不会仅增加来源白名单。旧目录、历史证据和生产认证保持各自身份。Q1产能累计复用尚未冻结，不能冒充第三个独立原格。

前批 CPI 的第四次全套实测为 379 passed / 1 failed / 276.36s。核心历史采集的收到时间为 23:18:16.301826Z，校验时间回拨到 23:18:15.976978Z，触发 acquisition_time_invalid。17项定向检查已通过，831全套仍未通过；全部失败记录保留，后续集中解决测试时钟依赖并统一验证，不把前批软件记录标为最终验收。

## 本批已验证进展

- PMI七月真实原件先因registered_source_contract_not_implemented失败；接入后1通过（5.26秒），8个独立审计值、双点时、选择和投影一致。
- 其余9家族真实原件全部复现拒收（9失败，25.46秒）；逐成员契约接通后，连同PMI共10通过（26.45秒），覆盖16指标、99个来源标量身份。不是99格重新逐值审计；完整审计仍引用前批逐值表，本批逐指标设独立数值锚点。
- 9项边界检查中8通过、1失败（12.16秒）：一月PPI和二月工业增加值合法缺列完整；错误提供方、成员、单位、期次类型和起止边界拒绝。OMO真实零操作原件仅生成金额声明，选择器不能沿用昨日利率的缺陷已复现；已补最新事件选择，正在扩大候选准入整文件验证。
- 5份已审边界原件从既有CAS复制到项目测试证据目录，703608字节逐一核对；[复制收据](evidence-official-consumer-edge/copy-receipt.json)。这不是新的网络获取或取得时间。

规格轴确认：研究说明中的9项required members、保留社融最低两成员、未来工具变化处理不是本次新增批准门，按既有源码和原件直接实施。Q1产能累计复用如何表达仍单独未冻结，本批新目录拒绝其ytd_rate，Q2三列正常可用。来源正式认证、真实模型和全量验收均未因此完成。

## 复审修复

候选准入整文件首次94通过（205.20秒）。后续两轴复审找到社融组成项漏要求8个stock_yoy，以及OMO选择/投影的鲜度分歧。社融初次反例把PUBLIC设在目标日之后，导致先被目标日过滤；该失败保留为夹具错误。改为PUBLIC=8月14日、SYSTEM=8月29日后，正确复现少8项仍complete；OMO371日事件误complete也同时复现（2失败/3通过，6.99秒）。独立11日OMO投影反例失败（3.59秒），证明其错误沿用daily的10日界限。

现仅社融总量保留最低stock_end+ytd_increment，组成项要求全部24成员。OMO消费者共用既有event的370日阈值；不增加新阈值、不把旧不合格事件回退成合格。缺1/8个组成同比、真实两页社融逐页补齐、各页原件/PUBLIC/SYSTEM保留、旧SYSTEM排除后页、Q1整批拒绝和OMO事件共8项通过（11.06秒）。两个拆页原件另复制56264字节，[收据](evidence-official-consumer-social/copy-receipt.json)，无网络或新acquisition。

规格轴原2项发现关闭、剩余0；标准轴原2项测试发现关闭、阻断0。来源定义字段比对的重复仍列非阻断可维护性建议。Ruff通过；mypy应用与候选准入测试85文件通过。全套尚未运行本批最终版本，不能沿用之前94项或CPI全套数字冒充最终验收。

## 已证实的测试时钟集中修复

根据4次全套采集时间回拨和静态默认capture调用链，在14个测试文件中为103个测试函数显式加入runtime_clock。无全局autouse；原函数体、断言、显式历史时钟、TTL/预算推进均保留。fixture只在被选入函数中使应用与测试侧datetime.now共用UTC锚点+monotonic，已经显式使用acquisition_clock/runtime_clock的用例不重复标记。

[第一份修改清单](verification-official-consumer/clock-opt-ins.json)含68函数，[搜索清单](verification-official-consumer/search-clock-opt-ins.json)含35函数。根代理执行一次性脚本后，标准轴独立AST核对103函数体与基点一致。test_source_history.py的pytest导入经Ruff重新排序，历史修改收据的原hash保留，最终验证以当前字节为准。7个涉及历次失败及检索的文件共174个参数用例正在关联验证；生产时钟和时间保护未改。

## 当前检查点：最终全量门保持开放

174项关联最终全部通过，859.55秒。随后完整856项执行为 **855 passed / 1 failed，3229.99秒，exit 1**。唯一失败为test_user_can_initialize_and_diagnose_an_offline_runtime的真实CLI子进程初始化超过测试60秒等待；没有时间回拨、来源契约或值计算失败。应用与测试均未为此改变，原60秒上限下该单例复测 **1 passed，6.20秒**。此结果支持“超时未在单例复现”，不证明整轮全绿，也不把未定位的机器耗时归因为已证的某个存储配置。

84个安装应用Python文件在该全套前后完全匹配。当前Ruff和mypy85通过，规格/标准阻断各0。保持full_gate_passed=false，继续其他明确来源入口缺陷，并在最终执行版本完成既有全量门；不为通过放宽CLI等待或生产时间保护。

[检查点收据](verification-official-consumer/checkpoint.json)准确保留855首轮通过、1失败、1独立复测通过。41份旧CPI及当前验证原记录（含UTF16/CR）先按原字节存入[原始记录归档](verification-official-consumer/original-checkpoint-records.zip)，再转换成便于Git审查的UTF8。两个预备finalize_batch.py均未执行，没有伪造final.json或实际来源/模型认证。

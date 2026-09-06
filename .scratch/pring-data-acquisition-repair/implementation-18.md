Execution: in-progress

# 18：CLI报告运行与解释证据

审查基点3cc9e8a；16已完成并提交2e08e18，513全套通过。13/14研究47份原件及两份报告已独立保存并做Git原件字节校验，认证/模型/切换仍未通过。

采用implement、tdd及完成后的code-review。测试缝为冻结EvidenceBundle→ReportService→真实CliReportAdapter→外部子进程替身→持久ReportRepository；另对实际已安装CLI做独立探针。既有历史冻结包只能用于隔离诊断，不是受隔离v3正式发布的许可。

已确认WSL codex-cli 0.144.4、Claude Code 2.1.191。现有Codex ignore-user-config/ignore-rules/output-schema与Claude safe-mode/json-schema均在当前help中，不能无证据删参数或沿用旧“未安装”结论。实施前ReportAttempt的adapter_version固定runtime-detected，缺退出码/实际模型/原输出诊断；现已修复。自然语言引用白名单校验不等于逐句语义支持。

## 已实现与验证中

- 两项公开ReportService→真实CLI替身进程→ReportRepository回归先RED，修复实际CLI版本、明确认证失败、退出码、CLI所报告的模型、提示/schema/输出指纹；无模型信息时保持not_reported。
- 真实Claude探针旧路径报cli_not_installed，但绝对路径版本和登录状态均正常。增加用户标准安装目录回退，公开接口反例RED→GREEN，按CLI自身订阅认证运行，模型厂商API key仍从子进程环境排除。
- 环境网络路由不应因密钥隔离而丢失：HTTPS_PROXY边界反例RED，修复仅传递标准代理/证书环境配置，不改变系统代理或写入厂商密钥。
- 取消反例表明旧代码会继续备用适配器并生成降级报告，已改为先记录取消尝试再停止；超时部分输出保留哈希，备用最多一次。首个取消fixture的备用超时忘设短值，主动停止后改为1秒验证，再得到明确RED，不用长等替代缺陷证据。
- Claude改stream-json+verbose以核验真实工具事件，StructuredOutput仅是共同schema输出；其他工具拒绝。Codex未知action（image_view反例）不能被四种工具枚举漏过，改仅允许被动reasoning/agent_message。两类工具反例均RED后修复。
- 解释核查单独追加不可变记录，绑定完整输出hash、冻结包hash和每段事实JSON Pointer/精确值、支持/反证与核查者。机器验证引用事实和覆盖，语义判断仍是具名逐段复核，不能把匹配指针说成自动理解了自然语言。原快照正文不改；API/页面独立展示初始结构引用校验和最新语义复核状态。
- 中间报告回归14通过、随后取消/工具18通过、段落核查19通过；mypy78通过。最终报告/Web组、全套及二路代码复核仍在执行，不提前标完成。

## 独立复核及修复

基点固定3cc9e8a。第一轮Spec发现3项、Standards发现1项，均以公开ReportService→真实外部CLI替身→持久报告入口复现RED后修复：

- 一个section包含多段时原实现会整体签署。共同schema/prompt版本升级为v0003，要求非空单段（拒绝CR/LF和Unicode行/段分隔），多段须拆为多个section；核查入口也拒绝为旧多段section整体签署。
- evidence_ids=null、嵌套对象和错误title类型原会抛TypeError或误收。先完整类型校验，再检查引用，失败尝试保存输出hash并按顺序备用一次。
- 原超时、非零退出和半截JSON会漏记已观察工具事件。先提取完整事件、记录未解析行数和Codex输出文件原字节hash/长度，再分类终态；失败内容不进入正文。
- 原版本探测另占5秒且不清理子进程。版本与生成共用一个适配器单调deadline，版本探测限于剩余额度内最多5秒，探测超时后不启动生成；取消/超时按进程组清理。真实替身启动子进程的两项反例覆盖清理、审计和不发布。

第二轮Spec发现v2冻结输入包经v3生成却被报告误标v2，新增旧包→新报告反例RED后修复：报告schema_version/prompt_version记录本次执行v3，input_schema_version/input_prompt_version从冻结包原文读取；提示和进程审计明确两种版本，旧包id/hash/document及历史快照不变。

最终静态复核Spec 0、Standards 0。修复后报告/Web 57通过，mypy78通过，Ruff通过；第一轮全套523通过，审查修复后的最终全套537通过（221.13秒），见[验证收据](verification-18/final.json)。初始_REPORT_SCHEMA保持原哈希，新表/字段通过0017增量迁移，曾出现的9项旧迁移哈希失败已修复，不能更新初始迁移哈希掩盖问题。

## 真实探针和外部条件

只读提取历史冻结包bundle-b8d0d3b7d18b284cf3f9，835,604字节、SHA256 44e6f39226dada99b01a1b7fceb68f61a9be715404b50d27da3110bd2e6ab7ba，目标日2026-08-03；原包完整保存，不代表最新目标日或来源通过。

- 完整包Codex：300秒单调时钟超时；Claude定位修复后同样超时。初始探针只保存进程输出指纹；trace版version与生成的输出文件路径相同，后一次覆盖了前一次版本输出文件，两个hash仍保留，应以response.process_audit和version元数据为准，不能声称该原文件同时支持两次输出。
- 独立聚焦包仅保留历史三核心状态、末日引用与治理限制，提示2,287字节，明确不解释省略的宏观/库存事实。首次脚本预备因bundle误写成函数调用而失败，尚未调用CLI；修复后新专属目录执行。Codex仍超时；Claude约4秒nonzero_exit，CLI报告model=claude-opus-4-8。这不是完整包解释验收成功。
- 两CLI状态分别是logged_in_chatgpt、claude.ai/firstParty；只保存分类，不保存账户身份或认证内容。直连HEAD：ChatGPT为Network is unreachable，Anthropic根路径403（仅证明该无认证HEAD得到拒绝，不推断具体订阅/额度原因）。
- Windows已启用127.0.0.1:10809代理且仅监听Windows loopback；WSL默认路由172.28.208.1，WSL loopback连接该端口被拒绝，现有WSL环境没有代理变量。已异步请求一个WSL可用代理地址；未改系统监听、开放端口或静默改走API。

真实合格AI输出仍为0，逐段真实解释验收保持开放。离线协议成功、确定性降级和网络诊断均不计为真实AI成功；后续不依赖网络条件的票继续执行。

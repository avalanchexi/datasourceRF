# 新目录 CPI 消费接入

基点 `395dde7`，票13/19的软件消费前置，实施中。沿用既有公开 CLI 准入、官方导入、EvidenceRepository 双点时查询、ModelInputSelector 与上下文投影测试入口。

## 行为和范围

新注册目录支持 `CN_CPI_HEADLINE`、`CN_CORE_CPI` 由国家统计局 `nbs_core_cpi` 家族消费。完整已审定义仍先经准入绑定；消费端核对来源代码、单位、维度、频率、发布规则/时区，并要求两项属于同一官方发布事件。单位仅 percent，类别分别为 headline 与 ex_food_energy，统计口径为 mom/yoy/cumulative_average_yoy。

新目录的完整性检查按统计月份要求成员：一月为环比/同比，其他月份还需累计平均同比。依据是[已完成逐值审计](p1-cpi-full-value-audit.md)的一月原表缺列；不补造累计值或 level。检索选择、Worker 就绪判断和版本评估复用同一成员规则，内置旧目录保持原行为。

没有更改旧不可变定义、实际来源认证、正式候选或生效指针。合成审查包只是软件测试身份；真实原件通过测试也不授予实际来源认证。本次软件指纹变化意味着后续正式准备须绑定新指纹，前批实件和收据保留。

## 验证过程

- 首个 RED：CPI 导入被 `registered_source_contract_not_implemented` 拒绝。
- 接入过程中还暴露总体 CPI 旧定义发布家族不同、模型成员契约缺失；分别按真实共同发布和成员身份接通后，7月纵向正例通过。
- 一月少累计列 RED：原文合法两列被判未补齐；按实际月份成员规则后两条正例通过。
- 8个身份/定义拒绝用例加入后，10项 CPI 检查通过。包括错误提供方、类别、measure、期次类型、单位，以及不兼容的已审来源代码、发布家族、allowed_units。
- 首次类型检查发现3处注解/类型问题，167项关联测试结束后已修，mypy85/Ruff通过。双轴审查要求的真实7月原件纵向和非一月少列反例已补，最终12项CPI通过；两轴复审0。
- 第一轮全套终态为 **2 failed / 644 passed / 371 errors，788.63秒，exit 1**。历史浏览器导入用例期间 UTC 从 `21:59:48.494574` 回拨至 `21:59:48.110903`，触发既有 `acquisition_time_invalid`；单例复跑通过不抹去失败。其后 C 盘实际剩余0，SQLite出现disk I/O，WSL停止并一度无法启动；没有把这轮记为通过。
- 第二轮在独立ext4测试卷通过13项恢复检查后，全套 **618 passed / 1 failed，1314.88秒，exit 1**。Treasury旧修订测试遭遇另一处UTC回拨，触发 `acquisition_availability_time_invalid`，磁盘I/O未复发。两个已失败测试现在显式使用递增的外部采集时钟，Treasury查询截点同步取该时钟；来源原件、修订前后值和失败保留断言均未删，生产时间保护未改。第三轮的14项针对性检查已通过（33.52秒），完整套件仍在运行。

所有 `verification-cpi-consumer-*.txt` 保留实际执行结果，名称含 green 不表示运行必然成功。全套结果未到齐前不标完成。

第三轮最终444通过/1失败/440.01秒。只读取证确认完整运行在商品采集响应后遭遇同一UTC回拨，触发worker_failure:ValueError:acquisition_time_invalid；原数据库及只读复制哈希、错误输出见verification-cpi-consumer/full03-forensics-02.txt。对应三参数测试显式采用统一的UTC锚点加monotonic时钟，采集、核心历史、Worker、运行记录和检索账本对齐，原断言保留。

第四轮先通过17个定向用例（115.70秒），随后全套379通过/1失败/276.36秒。核心历史采集正例received=23:18:16.301826Z、validated=23:18:15.976978Z，再次证实时钟回拨，非CPI值/契约失败。停止逐个故障后重复完整全套，集中静态审查实际默认capture路径的测试时钟；在其余16项消费者批完成后统一验证。verification-cpi-consumer/finalize_batch.py 尚未执行，不存在全套通过收据，不宣称本批最终验收或提交。

## 测试空间

本批清理的唯一既有运行目录为 `/home/tywin/.cache/pring-cycle/verification/catalog-full-final-02`。它是前批已结束的819项全通过 pytest basetemp，核对终态日志、绝对解析路径及进程命令行无该目标路径后，删除2349个文件/401,929,733字节；原测试日志保留，见[回执](verification-cpi-consumer/previous-suite-cleanup.json)。进程检查只覆盖cmdline，未扫描fd/cwd，不把它写成对所有占用方式的证明。没有删除用户 `.tmp`、失败现场、LPR实件库或生产数据。

[首次清理记录](verification-cpi-consumer/previous-suite-cleanup-original.json)保留原先过宽的 `active_use:false` 表述；当前回执只纠正证据表述范围，没有补做或补造历史fd/cwd检查，也没有再次清理。

### C盘耗尽后的恢复

5个旧Codex安装压缩包经精确路径、近期改动、进程引用及独占读取检查后，转存到项目 `.tmp/codex-install-cache-recovery-20260908/`，保留全部348,959,121字节并逐一校验SHA256；原路径和迁回依据见该目录 `manifest.json`。没有删除压缩包、主运行时或其他用户资料。[恢复脚本](verification-cpi-consumer/recover_codex_install_cache.ps1)是一次性记录，不要重复执行。

WSL恢复后根文件系统挂载为rw；一次 `fstrim /` 成功但未释放足够Windows物理空间。CPI导入收据的只读复核再次通过（9请求、18制品、46标量），不补写历史时间。

恢复试跑01被既有 `runtime_must_be_outside_source_tree` 拒绝；试跑02在 `/dev/shm` 通过历史浏览器用例，但其4.9GiB可用容量触发 `capacity_stops_worker_writes`。两次失败日志完整保留，应用路径及容量保护均未修改。后续使用独立D盘文件形成WSL原生ext4测试卷，真实来源导入库和生产运行路径保持原位。该卷仅容纳隔离测试数据，日志和代码身份仍保存到项目中。

测试卷文件为项目 `.tmp/pytest/cpi-native-volume-20260908.ext4`（32GiB），挂载点为 `/home/tywin/.cache/pring-cycle/verification/cpi-native-volume-20260908`。WSL挂载未跨调用保留，使试跑03被权限拒绝；随后[运行脚本](verification-cpi-consumer/run_recovered_suite.sh)在同一次调用中挂载、以tywin执行测试并退出卸载，实际ext4约30GiB可用。该脚本的新测试目录、指纹文件均拒绝覆盖；第一次脚本的指纹重定向中断窗口已在终态后修复，没有修改在途脚本。不要格式化或覆盖现有卷/测试目录，也不要将其加入Git。

[恢复后只读数据库检查](verification-cpi-consumer/recovered-import-databases.json)证明两个真实导入库的quick_check均为ok，并核对CPI/LPR合计36个原件及标准化制品哈希。WSL重启后代理仍仅监听Windows `127.0.0.1:10809`，WSL路由仍为 `172.28.208.1`；没有重复模型请求、改网络监听或将此核对称为AI成功。

## 后续已具备的具体输入

[其余16项官方消费契约](remaining-official-consumption-contracts.md)经根代理独立核对37输入、75本地链接。16项新目录certified入口仍拒绝，其中9项缺模型成员契约；10家族可用8份原件组织纵向测试，另5份验证缺列、合并期、精确金额、OMO零操作和Q1映射边界。该研究没有新增1812格审计、来源认证或真实模型。Q1源列复用仍未冻结，其他已有源事实按原件实施，不泛化增加批准门。

[CNY030新入口排查](cny030-official-next-boundary.md)经根代理10输入/22链接核对：3个新官方GET均200，最终指向000012母指数，目标日CNY030有效实值仍0。没有重复旧失败地址，也没有把3/3研究传输成功计为Tavily/Exa命中。

## 真实来源准备

[CPI认证前置研究](cpi-certification-next-boundary.md)经根复核7输入/8原件/8时间一致对/24引用。国家统计局公开统计数据的下载使用已有官方正面条款，不再列为泛化许可缺件。原页分钟时间有据可用；具体无新发布时间的实际修订另审，不一律清空所有历史PUBLIC。

新隔离运行目录 `cpi-document-import-20260908` 中完成8次真实document_import，46个标量逐项对照既有独立字面审计；另1次有界官方条款GET200，保存127,670字节原件（`fcb330d080046d9700e53c9a6416b3a97ca52a5cea770e7d467c2ea98589b5fe`）。这补齐研究阶段未保存的条款原件，不重抓8个数值页。

[9份实际收据](evidence-cpi-import-20260908/receipts.json)为44,462字节，SHA256 `f52846aa489ccb15a67d76573f5dffd54158a80edc1f99fb98e240e3557f2763`；独立[只读核验](verification-cpi-consumer/import-verification.json)核对9个数据库请求、18个导出制品及实际时钟/登记引用。声明、认证、真实候选、生产写入仍0；完整定义/manifest/certified_from/六项review绑定及真实模型采用仍需后续完成。没有恢复旧SYSTEM取得时间。

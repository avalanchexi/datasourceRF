Execution: completed-code-batch

# 14续：EIA公开日历史候选取得

实施基点 `b58d8a641b20f1f2bb2d7d34cddb2a6458cf07b1`。直接承接[已核验HTML契约](eia-html-contract.md)，按已接受的implement / tdd / code-review推进；不新增业务规则或改写旧目录。前批580项全套通过、真实中间价/GDP9项候选和研究原件保持原样。

## 本批行为

新增公开`refresh_eia_history`与CLI `eia-html-refresh`，各次请求固定RBRTE或RWTC官方日页，禁止隐式重定向。复用请求前登记、原件、标准化、来源声明和SYSTEM完成时钟；成功/失败的最终URL、HTTP状态、媒体类型独立留存。HTTP错误体保存后拒绝；网络未收到响应不造原件。

全表检查标题、系列、单位、Mon–Fri列、周起止、相邻周连续、重复日期、单元格数量及跨度；规范化空白不压缩日期坐标。官方每五周插入height=3的六格空白排版行，只识别这种明确布局行。请求窗口以实际日期取值，跨年及窗口外负数不会错位；NaN/Infinity和无法识别标记拒绝。HTTP/HTML声明字符集归一校验，当前支持UTF-8/ASCII，冲突或不支持者明确拒绝。

数值0与负值保留；空、`-`、`--`、`NA`、`W`在标准化候选中分别留原因和原始日期，只有数值生成分析声明。空窗口返回missing_values，condition区分源日期格无数值与窗口没有源日期格。源批次Release/Next Release Date和Eastern时区单独保存，不给历史日值填公开时间。所有新HTML声明强制awaiting_source_certification，真实SYSTEM时间按收到、校验及声明写入完成记录。同日新响应形成新版本，旧原件/旧SYSTEM视图保持。

既有API数值解析移除无来源依据的正数/1000上限，保留有限数值校验，额外拒绝布尔值；解析版本升为eia-spot-parser-v0003。官方2020-04-20 RWTC现货原值−36.98为负值反例依据，不拿期货新闻替代现货证据。

CLI复用现有写入门禁。目前完整Worker自动渠道仍按已有API配置执行；HTML命令为新候选来源准备入口，不冒充已认证自动替换或新模型生效。操作示例已加入[运行文档](../../docs/development/local-runtime.md)。顺手修正同页已过时的“搜索仅保存URL”描述，与已完成15–17行为一致。

## TDD与审查账本

- 新HTML公开接口缺失：RED1失败0.73秒。实现后的三个真实样本首轮3失败5.19秒，定位为官方height=3空白排版行，按真实结构处理，未改官方原件或期望值。
- 新CLI入口缺失：RED1失败2.64秒。旧API拒绝官方负值的传输形状反例：RED1失败1.16秒；该测试明确不是实时API响应。
- 初次HTML/API相关29项通过26.93秒；添加真实网络失败及布尔/非有限数值反例后，相关37项通过50.61秒。
- Standards发现整周删除和合并格可通过。三个公开刷新反例真实RED3失败4.06秒；增加相邻周连续和非1跨度拒绝。正常空周仍保留日期格。
- Spec发现字符集、响应身份未落库、空窗口返回假成功。字符集/空窗口4反例真实RED5.09秒；错主机失败后响应身份缺失RED1失败1.85秒。现在成功响应身份写标准化与取得记录，失败写取得记录；声明charset校验及空窗口返回状态均修正。
- 最新针对测试 **42通过、49.20秒**，见[输出](verification-14-eia-final-targeted.txt)。Ruff通过，mypy80个源文件通过；最终Spec和Standards均0项问题。全套结果待完成后追加；以上不等于来源认证通过。

## 真实公开CLI取得

在独立新库 `/home/tywin/.cache/pring-cycle/verification/repair-14-live-eia-20260907a` 执行两次公开CLI，真实GET各日页一次，请求窗口2026-08-24至2026-09-04。Brent6个数值/4个空格，WTI7个数值/3个空格，全部原始字段逐项与研究原表独立期望相符。Brent96.02保持09-01而非08-31，WTI09-01=91.48。

两份原文和两份标准化制品、13项声明关联、7个空格、响应身份及真实SYSTEM时间通过[独立导出复核](evidence-14-live-eia/delivery-verification.json)。原文哈希与此前研究相同，但本次有独立请求和取得时间。公开时间均未知，认证均awaiting；实际模型采纳、生产写入及模型激活均0。见[完整结果](evidence-14-live-eia/result.json)和[可重算检查](evidence-14-live-eia/verify_delivery.py)。

工具回传曾异常延迟约23分钟，四个子任务本身返回的是42项测试49.20秒、mypy/Ruff通过和两次真实GET成功；未将回传等待计成HTTP耗时、测试耗时或来源失败。精确请求时钟以取得回执为准。

## 全套回归中断：运行环境存储故障

首次全套运行198.05秒，pytest报告347通过、1失败、529个setup/teardown错误（错误数不是不同用例数）。首个失败发生于`initialize_runtime`的SQLite迁移，在调用EIA刷新前即出现`disk I/O error`，随后Python捕获、临时目录创建等连续出现`[Errno 5] Input/output error`。完整[失败输出](verification-14-eia-pytest.txt)保留；不能将42项针对测试当作全套通过。

当场Windows检查C盘可用0字节，D盘可用265,884,774,400字节；`wsl --list --verbose`显示Ubuntu-22.04及docker-desktop均Stopped。Linux空间与内核日志查询无法启动，分别收到E_UNEXPECTED和CreateInstance/E_FAIL，因此未声称查明Linux内部磁盘状态或由应用造成。已请求恢复C盘空间，未删除或移动用户系统文件。恢复后需检查运行环境和已安装源码，再以新测试目录/新日志重跑完整套件；本批暂不提交、不记录完成。可独立核查D盘已导出原件，继续来源研究。

各项已通过结果与本次失败分开保存于[验证状态](verification-14-eia/verification-state.json)。此前580项通过的提交仍有效，但它不包含本批EIA HTML接入。

D盘导出重新独立检查通过，见[归档复核](verification-14-eia/archive-verification.json)：4份原件/标准化制品SHA逐字节一致，13条候选值与独立日期期望和请求关联相符，7个空格未压缩；80份工作区Python文件与故障前已安装验证的指纹一致。这只是保存文件的复核，未重验WSL已安装包或活动数据库，也没有新的HTTP/数据库写入。复核命令：`C:/Python313/python.exe -B .scratch/pring-data-acquisition-repair/verification-14-eia/verify_archive.py`。

### 恢复后继续的准确入口

先确认宿主空间、WSL文件系统可读写及本项目解释器可启动；保留本次失败日志和测试目录。对本批真实候选库作只读完整性检查，不复用演练脚本原路径重复抓取。依赖同步仍使用已锁定、离线、非editable安装；重新验证安装包与工作区身份后，以新的native测试目录重跑，不能从347项处跳过前面用例。

```powershell
wsl -d Ubuntu-22.04 -u tywin --cd /mnt/d/cursor/datasourceRF env UV_PROJECT_ENVIRONMENT=/home/tywin/.local/share/pring-cycle/dev-venv /home/tywin/.local/bin/uv sync --locked --offline --extra dev --no-editable --reinstall-package pring-cycle
$eiaRecoveryId = Get-Date -Format 'yyyyMMdd-HHmmss'
wsl -d Ubuntu-22.04 -u tywin --cd /mnt/d/cursor/datasourceRF env -u PYTHONPATH /home/tywin/.local/share/pring-cycle/dev-venv/bin/python -m pytest -q --basetemp="/home/tywin/.cache/pring-cycle/verification/repair-14-eia-recovery-$eiaRecoveryId" --tb=short | Tee-Object -FilePath ".scratch/pring-data-acquisition-repair/verification-14-eia-pytest-recovery-$eiaRecoveryId.txt"
```

以上命令分别检查退出码，先等待安装结束，再运行测试。新结果另写收据；全套成功、静态检查与复审仍有效且暂存原件哈希通过后，只提交本批明确文件。`dashboard.css`、`dashboard.js`、玻璃样式任务目录及其他无归属临时文件继续排除。恢复前不把环境失败改成通过或关闭整票14。

## 环境恢复后的最终验收

宿主C盘空间恢复后，WSL正常启动；锁定离线非editable安装成功，80个源码文件与故障前指纹逐一相符。两个隔离候选库的SQLite quick_check、foreign_key_check通过，8份原生CAS制品与D盘导出逐字节相同，native写入探针通过，见[恢复检查](verification-14-eia/recovered-runtime.json)。未读取生产库或建立数据库副本。

全套重新执行 **612通过、0失败，768.67秒**，见[完整恢复日志](verification-14-eia-pytest-recovery-20260907-164621.txt)及[最终收据](verification-14-eia/final.json)。此前42项针对测试、Ruff、mypy80、Spec/Standards复审均通过且应用源码没有再改变。最初存储故障失败日志和收据保留，恢复结果另记；工具结果回传再次出现长延迟，不将其混入pytest报告时长。本批代码验收完成，整票14仍in-progress。

下一Treasury纵向用例放在`.scratch`草稿测试目录，未纳入本次默认612项；公开接口缺失真实RED1失败3.53秒，待本批提交后接续实现，不将下一批草稿称为当前通过覆盖。

## 后续门槛

等待环境恢复期间，另完成[Treasury官方CSV/方法补证](treasury-followup.md)。3个实际GET均200，342个收益率字段与旧官方HTML一致；根代理用Windows标准库重跑交付校验通过，原件和报告SHA已核对。它为下一候选渠道与鲜度规则提供依据，未替代官方适配器实施、来源认证或历史公开时间证明。

本批完成公开候选渠道接入代码，不完成票14全部来源/发布日历/鲜度认证。EIA批次日期不能证明120日历史首次PUBLIC；SOURCE日历与中国120交易日仍分开。新目录/模型认证与采纳归票19依赖，旧v3否定性审查保持；真实Tavily/Exa配对实测、PUBLIC重放、真实CLI报告解释和真实切换仍各自待验。

Execution: completed-code-batch

# 14续：Treasury官方CSV候选接入

基点为`abbeb01`，前批EIA全套612项通过后提交。直接承接[已核验来源契约](treasury-followup.md)，沿用票14已接受的公开采集/查询/CLI测试边界及implement、tdd、code-review。

## 本批行为

新增公开`refresh_treasury_yields`与CLI `treasury-csv-refresh`，一次限定一个来源年度CSV，窗口可小于年度；跨年或逆序窗口在请求前拒绝，应分年调用。固定官方名义曲线URL以及`Date`、`2 Yr`、`10 Yr`字段身份，验证最终URL、HTTP状态、CSV媒体类型和字符集。请求开始登记、响应原件、标准化制品、声明身份和实际SYSTEM完成时钟沿用现有采集协议；HTTP错误体仍保留，未收到响应不制造原件。

全年度检查表头唯一性、行宽、日期格式、来源年度和日期重复；目标字段须为有限普通十进制数，按官方名义CMT零下限保留0并拒绝负数。空字段、N/A分别记录原因和原始字符串，只有数值形成声明。按来源实际日期取窗口，不制造节假日记录；有效年表但窗口无行返回`missing_values`和明确原因。来源最新期次按两个指标分别记录，历史窗口不冒充源的最新发布期次。

声明保持`awaiting_source_certification`、PUBLIC未知；来源时区为America/New_York，实际取得和校验后记录SYSTEM。修订形成新取得与新声明；若后续响应为N/A，保存新缺值收据、原N/A和旧有效声明的真实身份及时间，不把旧值计作本次新取得，也不制造来源没有声明的撤回事件。入口复用既有CLI写入门禁，使用示例见[运行文档](../../docs/development/local-runtime.md)。

## TDD与审查账本

- 首个公开接口用例先在.scratch草稿目录运行：模块缺失，真实RED **1失败、3.53秒**；最小实现后 **1通过、2.70秒**。该草稿未计入前批612项，随后移入正式integration目录。
- CLI缺失：RED **1失败、2.00秒**；补入口后 **2通过、3.49秒**。
- 历史窗口遗漏来源最新期次：RED **1失败、1.79秒**；补逐指标来源期次后 **3通过、3.96秒**。
- 边界集 **25通过、19.65秒**；最终加入旧值后N/A及真实HTTPError传输形状两例后 **27通过、17.06秒**，见[最终针对日志](verification-14-treasury-final-targeted.txt)。覆盖真实样本、公开CLI、换序字段、0/缺值、非法响应身份/媒体/字符集/表结构/日期/数值、修订、网络失败、空窗口及旧值保留。
- Ruff通过，mypy **81个源文件通过**；非editable安装的81个Python源文件与工作区按LF逐字节一致，见[指纹](verification-14-treasury/code-fingerprint.json)。
- Standards最终0项；Spec最终0项。Spec最初提出后续N/A是否应撤回旧值的疑问，按票14“已有有效值保留真实期次”收口后撤回该项；只增加可观察行为回归，没有为此引入未授权的撤回规则。两项审查后应用源码未再改变。
- 全套回归在新native目录执行，**639通过、0失败、800.47秒**；见[完整日志](verification-14-treasury-pytest-20260907-174432.txt)和[最终收据](verification-14-treasury/final.json)。此次实际退出码0，源码在安装、审查、真实演练与全套之间未再改变；此前EIA的612通过没有替代本批全套验收。

## 真实公开CLI演练

在新native候选目录`/home/tywin/.cache/pring-cycle/verification/repair-14-live-treasury-20260907a`执行1次公开CLI和1次真实GET，窗口2026-08-24至2026-09-04。官方CSV产生10个实际来源日、20条待认证数值、0缺值；09-04两年期4.37%、十年期4.78%。逐日数值均与此前研究独立期望相符。

原件SHA为`a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5`，13,961字节；标准化SHA为`e6c3fb3d34c90f5fa115971f32dc755020a11d9d8983b65e29c72d61d4d7d10f`，3,194字节。新请求有独立取得时间，虽原文与研究相同，也没有沿用研究时间。[独立复核](evidence-14-live-treasury/delivery-verification.json)通过2份制品、20条声明和原件链接、实际SYSTEM时间及未知PUBLIC；验证脚本默认只读、不联网，见[verify_delivery.py](evidence-14-live-treasury/verify_delivery.py)。实际来源认证、模型采纳、生产写入和激活均0。

## 未完成边界

本批完成官方CSV候选入口；自动Worker仍使用既有渠道，来源认证和源日历鲜度另行验收。官方“通常18:00前可用”只支持预期，不能填历史首次公开时间。未创建新目录/模型或派生利差的正式模型结论。

同期[VIX补证](vix-followup.md)核验CSV CLOSE，但早期未使用OPEN字段有47处异常，且16:15计算结束、付费数据文件交付窗口都不能证明该公共CSV历史PUBLIC。持续生产使用范围仍需明确记录。整票14保持in-progress；Tavily/Exa配对实测、120个中国交易日PUBLIC重放和真实报告/切换分别沿原依赖推进。

# 01/02 增量两轴审查

## Standards

**Standards：01、02 增量均无新增发现。** 已逐项应用技能全文的12项 Fowler smell 基线，仓库规范优先，未重复报告工具已覆盖项。

固定证据已核：三个当前文件 SHA-256 全部匹配；两树 HEAD 均为 `bb737200024369f2938d26d1cc49f5f77f18a1b1`，无新提交；实际差异非空。旧快照及还原文件哈希一致，已排除此前审查范围。

- **01：0项。** [新增夹具标记](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/tests/models/test_material_preflight.py:525)复用单调推进的外部时钟，符合 `docs/agents/testing.md` 的时钟替身规则；未改变发布时间、真实解析、时序守卫或原断言。生产源码与r3一致。原失败日志确认系统时间倒退；r4现有日志为36 passed／104.95秒，终态exit 0、身份不变。本次仅核阅收据。

- **02：0项。** [六行守卫](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-02/src/pring_cycle/candidate_admission.py:253)使用冻结目录的核心角色及 `source_codes` 比较，符合ADR-0020“三核心身份不变”；不会依赖请求自报角色规避检查，也未扩展至旧迁移分支。[参数化CLI反例](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-02/tests/models/test_cny030_optional_migration.py:139)覆盖三种核心替换，重新绑定审核后断言专项拒收及模型列表不变；合法路径明确核对三核心源代码。现有收据为91 passed／37.65秒，主代理身份核验记录103个安装文件一致。

仅审Standards，未审Spec；未委派、改文件、运行测试、联网或读取凭据。报告、完整Worker及旧发布历史缺口仍未完成；本结论不代表整票验收，最终判断与验收权归主代理。

## Spec

仅审 **Spec 轴：01、02 本次增量均无新发现**。

已读 code-review 技能、项目规则、完整父规格及两票。三个当前文件哈希首尾核验一致；两树均停在 `bb737200…`、无新提交，指定工作区 diff 非空。已核对旧审查包并排除已审范围。

- **01：时钟修正符合规格。** 票01要求“核对…PUBLIC 和 SYSTEM 截止语义”，并允许替换外部时钟。[唯一新增装饰器](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/tests/models/test_material_preflight.py:525)使用单调推进时钟，未改变发布时间、原件损坏、真实获取/解析/选择或断言：08-28仍隔离尚未公开的坏修订，08-31仍报告缺口。删除该行后的哈希及其余文件均匹配r3。失败日志确认此前在采集时序检查处因时钟倒退中止；现有r4证据为36 passed／104.95秒、exit0，前后软件、安装及材料身份一致。

- **02：核心源身份准入缺口已补齐。** 票02要求“改核心/角色/源身份…均被拒；三核心仍为000985、000012、NHII”。[新增守卫](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-02/src/pring_cycle/candidate_admission.py:253)依据冻结目录的核心角色比较`source_codes`，结合既有ID、角色及映射检查，覆盖三核心身份。公开CLI反例分别替换为000300.SH、CNY030.CS、NHAI.NH，重新绑定审核后要求拒收且模型列表不变。守卫仅作用于此次专项迁移，不改变历史迁移规则；合法迁移读回保留三核心代码。现有相关收据为91 passed／37.65秒，主代理核验103个安装文件一致。

02原有三项未完成仍保留：**报告证据白名单、完整Worker完成链、旧声明及已发布投影/报告不可变证明**。它们不是本轮新发现，不据此阻止已完成准入切片集成，也不将准入修复等同整票完成。

未改文件、运行测试、联网、读凭据或委派；最终判断与验收归主代理。

Standards 0项；Spec 0项新增。02报告/完整Worker/历史保护缺口继续开放。

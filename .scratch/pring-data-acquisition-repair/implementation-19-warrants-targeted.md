# 八品种仓单定向取得

基点 `96964cf`。本批接通 `CN_FUTURES_WARRANTS` 的日频定向取得，范围为既定 CF、CU、PP、RB、RU、SC、SP、TA；TA 沿用接口侧 PTA 映射。

请求复用现有账本、原件捕获和整批入库逻辑。每次物理请求分别记录，瞬态失败最多尝试三次。整批中途失败时，已接收原件保留并标记批次失败，不形成部分来源声明。不将取得时间写成历史公开时间，也不以收到原件代替正式认证。

## 验证

- 公开任务提交→Worker→账本和证据查询：正常八次请求、27个字段点；PP前两次失败后恢复共十次请求、27个字段点；PP三次失败共五次请求、零个新字段点，已收到的CF/CU原件仍可读取。
- 所有新字段点只关联自身品种的确切物理回执；未知PUBLIC仍为未知，任务保持 `action_required`，账本不含测试密钥。
- 夹具使用隔离的旧v2模型生命周期验证任务路由和持久记录，数量与单位明确为合成值；未绕过新候选正式门禁。首次v1夹具因三维旧契约与四维新仓单不匹配而拒绝入库，修正夹具后通过，未修改该拒绝规则。
- [最初RED](verification-warrants-targeted-red-01.txt)复现未发出仓单请求；[取得及三种重试分支](verification-warrants-targeted-retry-01.txt)3项通过。[关联回归](verification-warrants-targeted-associated-01.txt)91项通过，925.14秒；最后仅改变测试类型和bytes断言后，[3项针对复测](verification-warrants-targeted-final-01.txt)通过，4.58秒。精确文件与终态绑定在[本批检查点](verification-warrants-targeted/checkpoint.json)。
- 应用[86文件mypy](verification-warrants-targeted-mypy-app.txt)、[Ruff](verification-warrants-targeted-ruff-final.txt)、[格式](verification-warrants-targeted-format-final.txt)与[安装源码](verification-warrants-targeted-fingerprint.json)通过。原集成测试文件的[基点mypy](verification-warrants-targeted-mypy-baseline.txt)已有38错误；修正新增类型后[当前文件](verification-warrants-targeted-mypy-03.txt)仍为相同38项，不能称该测试文件整体类型检查通过。保留首次39错误、格式和导入失败记录。
- Spec轴0项、Standards轴0项，均为独立静态审查；不代替测试终态。

本批没有真实付费请求、生产模型激活、实际120日重放或切换；日预算和费用规则沿用既有实现，物理请求次数不冒充账单。下一步修复Worker对历史完整仓库成员的覆盖统计。真实PP/CF/TA来源、历史公开时间及整个候选前置仍未完成。

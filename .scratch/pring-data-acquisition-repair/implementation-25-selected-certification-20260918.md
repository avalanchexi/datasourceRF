# #25 双通道认证与选中声明断言（2026-09-18）

Status: component-validation-passed-heavy-pending

在既有 CPI、PPI、PMI×3、M1/M2、SF、GDP 回归中，按点的 selected_claim_id 核对交付方及 certified；投影行必须非空、恰有一个选中声明，再核声明与行级 certified。消除旧 all(... if selected) 在声明列表为空时也会通过的漏洞。TuShare 与官方期次和值的原断言保持；GDP 历史 PUBLIC 缺发布时间仍不允许采用。

[本次65项相关回归](verification-25-selected-certification-20260918.txt)全部通过171.96秒，命令及真实退出码0附日志。包含公开负缓存反例：首轮三个实际失败请求，TTL内第二轮复用明确的失败请求、无新增物理HTTP，不把 RetrievalBudgetBlocked 一概当网络失败。

## Standards

硬违规0，判断项0。两个helper分别验证真实证据点及输出行，无内部行为替身；非空和唯一采用声明先行，再核身份。它们属于测试输入，不属于生命周期材料构建依赖；最终测试指纹必须包含。

## Spec

无新增阻断项。八项双通道认证身份组件要求已覆盖；原有缺口、原件、失败语义及PUBLIC边界未削弱。重型Worker测试也已准备对应投影/报告断言，但当前版本尚未运行，不能据此关闭投影/报告端到端、输出留痕变异或真实来源认证条件。

旧#25/#27监督重跑终态为1通过、1失败（1528.77秒）。失败为测试把TTL负缓存的合法拒绝误限定为OSError；已由公开获取反例和持久化ledger核实，并加强重型测试为验证准确的复用请求、TTL及没有额外物理HTTP。旧终态保留，不改写为通过。新版本完整Worker、缺P0、输出变异和最终完整套件仍待执行。

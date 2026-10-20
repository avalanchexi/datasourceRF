# ECB 交付切片两轴审查

工作树 `/mnt/d/cursor/datasourceRF-p2-20260917`，固定基点
`06bccc3781d03a776743663f946c49ce3f23caae`；新增/修改内容覆盖同日双腿导入、HTTP 获取、
不可变修订、来源契约、CLI 和投影原件复核。规格见 `decision-27-ecb-reference-cross-20260917.md`
与 `plan-27-ecb-delivery-20260918.md`。依 code-review 技能，由独立 Spec 和 Standards 代理只读审查。

## Standards

初审发现 HTTP `IncompleteRead` 不属于既有捕获类型，获取失败缺少分类与部分正文留存。
公开反例先失败，现保留有界 partial、真实 HTTP 状态与 `complete=false`，记录 `source_failed`。

判断性建议为逐条声明重复复算完整 ZIP。现使用最多 4 项缓存，键为 raw、normalized 的完整字节
及解析上下文；每次仍先读取并核对两个原件哈希、检查回执身份。原件改变不能复用旧证明。

最后限定复审：未发现新增硬问题；长度核对使用共享规则，采集和原件复核均以实际 `len(raw)`
校验。新增公开反例检查短体、原件和失败分类；CLI 正例含精确 Content-Length。

## Spec

初审同日双腿、34 位十进制规则、完整原件与规范化对照、重复/修订及 PUBLIC 约束无硬问题。
后续复审发现标准库 `read(size)` 在部分 Content-Length 短体情况下直接返回，完整可解析 ZIP
仍可能被采用。公开反例先得到 DID NOT RAISE；现同时保留声明长度并在采集和证明复核中核对
实际长度，不允许只改 `complete` 绕过。最后限定复审无新增规格硬问题。

## 验证范围

代理均未编辑或运行测试。两项确定性问题已修复，重复整档解析建议已处理；最终回归以
`verification-27-ecb-delivery-v2-installed-final-20260918.json` 为准。第一轮旧安装包 156 项通过
只绑定修正 Content-Length 之前的代码，不能替代 v2。

真实认证、完整 Worker 接线及目标交易日下 SYSTEM-only 使用边界仍属后续工作；本审查不宣称
整票完成，也不替代真实候选、120 中国交易日回放和显式激活/切换。

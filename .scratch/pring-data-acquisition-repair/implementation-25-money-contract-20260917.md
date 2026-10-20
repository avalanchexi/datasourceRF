# #25 M1/M2 四成员交付契约阶段

工作树 `/mnt/d/cursor/datasourceRF-fallback-20260917`，比较点 `e19834e280175afe6ce1c8b52d1eabc4a1faea12`，提交 `07bd8f9fd6cf8e1f4c53f1bbe6acfccf75c0a2e8`。四源文件及一个新测试文件。未合并、推送或激活。

## 行为与明确未完成项

新不可变定义显式声明 `tushare:cn_m:official-sampled-v0001`，通过 money(include_month_on_month=False) 精确请求 month,m1,m1_yoy,m2,m2_yoy，保留已有必需四成员与单位（余额亿元、同比百分比）。旧默认六字段和历史定义保持不变，新契约拒绝未纳入官方共有口径的环比字段。

TuShare 原件按精确字段、API、范围、receipt、整份规范化结果复算；无独立证据的 PUBLIC 时间拒收。已有本期四值保留原来源声明及值；缺期时从真实人民银行列表定位报告，采用官方四值并在 credit.evidence 显示渠道；双方失败保留缺口、获取尝试及物理请求失败分类。

**Worker 自动刷新尚未传新四字段参数，当前不能宣称完整自动交付已经接通。** 后续以完整 Worker 公开红例接线，并与 SF/GDP 统一冻结验证。具体下一步见 plan-25-remaining-families-20260917.md。该方法参数及 marker 不授予真实来源认证。

## 验证

- money-contract-red-valid：新增四字段请求参数原先不支持，实际 TypeError；此前 money-contract-red 仅是夹具误用 tuple.append，修正测试后重新取得真实红例，没有据此改生产代码。
- 初次交付路径 1 passed in 3.46s。扩展双方成败矩阵时三通过、一失败：测试误把缺口说明行当作没有投影行；按既有 value=None/claims=[] 行为修正，未改产品行为。
- 四个成败阶段用例、三个原件/伪 PUBLIC/旧字段反例，以及旧 TuShare 适配器合计 28 passed in 20.05s。字段的合成不同值与真实官方值分别验证，原件来自归档 pbc_money.html。
- 复审整理重复契约分支后重新构建独立离线 wheel；**158 passed in 80.21s，exit=0**。源码/安装 99 文件与 11 个测试文件在运行前后未变，verification-25-money-installed-final-20260917.json。日志 SHA256 3f0600ccd603a946db243292aa5fd3b5f97fb39f0350f5b29dac96019758f6ba。会话 76558 已结束。
- Ruff、四源文件 mypy 和 git diff --check 通过。

## Standards

独立复审未发现硬问题。初审一项 Repeated Switches 判断性建议已修：同一个分支一次性选择 contract、api、delivery_fields，不再先生成 PMI 字段后覆盖。限定最终复审确认建议解决，无新增问题；只读审查未替代测试执行。

## Spec

独立复审未发现本阶段新增硬问题或领域口径偏差。四成员及单位与既有官方/必需契约一致；新鲜度回退保持已有值，失败与来源均可观察。Worker 尚未选新参数、完整运行状态与真实认证是明确后续缺件。

## 后续与资源

CPI、PPI、PMI 三指标及 M1/M2 共六项已有阶段契约验证，SF 总量、GDP 两项待处理；M1/M2 的 Worker 接线仍开放，不能按六项完整交付计算。新输入完整 Worker、来源认证、真实新目录候选、120 中国交易日回放、显式激活与切换均未完成。主目录原 WIP 未覆盖。C 盘仍 14GB，原生盘 832GB 可用；pytest 临时文件 195MB、可复用测试材料 5.9GB，不删除这些材料导致重建，未做清理。

# #25 社融总量交付契约与阶段回退

工作树 `/mnt/d/cursor/datasourceRF-fallback-20260917`，固定比较点 `07bd8f9fd6cf8e1f4c53f1bbe6acfccf75c0a2e8`，提交 `e2fd6a29c3ed951e84e1bdb5d4b7bae42419a722`。六个代码及测试文件，409 行新增、7 行删除。未合并、推送或激活。

## 行为

新不可变定义显式声明 `tushare:sf_month:official-sampled-v0001`。新 social_financing_total() 只请求 inc_cumval、stk_endval 两个官方共有必需成员：累计增量 year_to_month 从当年 01-01 起，存量 month 并由万亿元转为亿元。旧三字段 social_financing() 和旧期间行为保留；新契约拒绝未纳入的 monthly_increment 和错误累计期间。

_Field.period_kind 默认 month；仅新累计字段使用 year_to_month。完整原件依据 API、精确字段、范围、规范化结果复算，PUBLIC 未有独立证明即拒收。该 marker 不授予来源认证。

人民银行金融统计目录扩展到社融家族，按期次定位真实报告，scope 只写总量声明，整页原件保留。已有 TuShare 本期两值时不因官方不同值改写；缺期则补官方总量（三值含非必需 stock_yoy）。无匹配目录不等于“未发布”，保持 validation_failed/ValueError 与物理 semantic_validation_failed；正文传输失败为 source_failed/OSError 与 transient_transport_error。两者都保留缺口。

## 红绿与最终验证

- verification-25-sf-contract-red：新交付入口原先不存在。实现后首次测试误读 MetricSeriesPoint 未暴露的 period_kind/unit，改为公开采集规范化内容/ClaimView 单位；只修测试。sf-contract-final：1 passed in 2.52s。
- sf-listing-red：目录未被识别，正文完全未被请求。扩展合法 family 后 sf-listing-green：2 passed in 7.77s。
- 六种双方交付/传输失败/目录无对应期次组合。第一次 no_matching_period 夹具把半年标题链接到七月正文，导致正常历史预热请求也命中同 URL；改为无相关链接的目录夹具，没有据此改生产逻辑。当前不把“列表无链接”称为确定尚未发布。
- 四种负例：损坏原件、错误累计期间、伪 PUBLIC、旧三字段。加旧 TuShare 及 M1/M2 共39通过61.99s；补两种实际 acquisition+月份绑定的失败分类断言后4 targeted通过21.49s。
- 新独立离线 wheel，**169 passed in 107.35s，exit=0**；99 源文件/安装、12 测试终态指纹均未变。verification-25-sf-installed-final-20260917.json；日志 SHA256 8fe398814bc67b8818145cc78230570b35a80c2cadeb21a84109f6f846e528e4。会话43789已结束。
- Ruff、五源文件 mypy、git diff --check 通过。

## Standards

独立只读复审未发现硬问题或非阻断气味。默认 month 保持，新增 family 单次选择契约/API/字段，整页原件与按指标写入边界一致。审查不代替测试执行。

## Spec

独立只读复审未发现本阶段口径偏差。初审所提“无匹配期次的账本分类”已补真实 acquisition+period 断言，最终限定复审确认闭环，未发现新增问题。

## 剩余

**Worker 尚未调用 social_financing_total，M1/M2 也尚未选择四字段参数**，留在后续完整 Worker 公开红例接通。当前七项重叠指标已有阶段契约，GDP 尚未；不能称七项完整自动交付。GDP、当前输入完整 Worker、可靠时间绑定、真实来源认证、新候选120中国交易日回放、显式激活/系统切换仍开放。详见 plan-25-remaining-families-20260917.md。主目录 WIP 与归档材料保留。

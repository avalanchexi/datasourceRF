# #25 GDP 名义交付与季度官方回退

完成此工程切片：2026-09-18 07:42 Asia/Shanghai。独立工作树 `/mnt/d/cursor/datasourceRF-fallback-20260917` 提交 `0946735d706257bef44009beb270188e0ee901a4`，基点 `e2fd6a29c3ed951e84e1bdb5d4b7bae42419a722`。未合并主目录、未推送、未激活。

新不可变定义可显式选择 `tushare:cn_gdp:official-sampled-v0001`。cn_gdp 原有精确九字段请求和 `tushare-gdp-parser-v0003` 保持；仅四部门 nominal_ytd_level 可采用，累计起点 01-01、单位亿元。gdp_yoy/pi_yoy/si_yoy/ti_yoy 继续以 `gdp_yoy_period_semantics_unverified` 拒收，不改称当季或累计实际增长。marker 本身不赋予认证。

ContextDelivery 统一接受标量与拒收记录。每份原件一次复核同时重建两者，核对完整规范化响应；即使仅选总量，其他部门规范化造假或拒收记录丢失、改名也使该原件不可采用。多个季度分批请求时，声明按每份原件实际包含的季度关联，拒收记录也保留在其自己的回执内。无可靠出版证据时仍保持 PUBLIC 为空，不能注入公告时间。

GDP 官方季度列表支持已取得的真实标题：Q1“一季度”、Q2“二季度和上半年”、Q3“三季度”、Q4“四季度和全年”国内生产总值初步核算结果。Q1/Q2 为2026年原件，Q3/Q4为2025年原件；精确 URL/哈希在夹具 README 中。只补缺少 TuShare 交付的指标期次；现有已发布旧季度下会另查上一完整季度，但未发布的新季度不被制造为必需输入。列表/正文请求各有原件、失败分类和物理请求账本。

GDP 原有八个必需成员未缩减。历史目标仍受既有 PUBLIC 边界约束：四个无公开时间的 TuShare SYSTEM 行能阻止新鲜度回退，但不能自动成为历史目标模型输入；不会为让完整运行通过而改此规则。未取得可靠历史日期的处理继续遵循已确认 #26 决定。

## 验证

- 正确设置合成认证候选后，对先前 SF 安装包运行新合同反例，得到 `registered_official_source_contract_unsupported`；之后新源码通过。最初测试误用带短横季度 API 参数、以及 P2 默认未认证夹具的失败已纠正，不作为实现缺口证明。
- 官方目录未接入、三季度短标题、新季度发现、双季度原件错绑、非法季度失败分类均分别保留先红记录；参见 `verification-25-gdp-*-red-20260918.txt`。历史目标下期待 SYSTEM 行直接被选中的早期断言也已纠正，未改变该质量限制。
- 最终 21 项 GDP 行为用例；与原 TuShare 适配器合计 **42 passed in 55.36s**，日志 `verification-25-gdp-reviewed-green-20260918.txt`。
- 新离线安装包 **190 passed in 143.47s，exit=0**。99 源文件/安装逐字节一致，13 个选定测试文件以及全部106个测试输入终态未变。回执 `verification-25-gdp-installed-final-20260918.json`；日志 SHA256 `40619d272749a488be2342de2e15f473364e95c29e43c49a7da58ccaad28d98c`。可重现过程见 `verify-25-gdp-installed-20260918.py`（新验证须换隔离目录）。
- Ruff、6 源文件 mypy、diff whitespace 检查通过。两轴审查修复了季度 KeyError、批次错绑及重复解析；最终无未解决发现，见 `verification-25-gdp-review-20260918.md`。

## 剩余范围

八项重叠指标均已有阶段交付/回退契约；M1 四字段参数、SF 新方法仍未接入 Worker。当前输入的完整 Worker 验证、实际来源认证/公开时间证据绑定、真实候选、120 中国交易日回放及显式激活/切换仍开放。旧 PPI 完整 Worker 通过不覆盖本提交。GDP 本身为 P2 背景项，不能靠缩减成员或伪造时间消除缺口。

本轮使用归档原件，新增来源网络请求为0。C盘从11GB降至约10GB；在线 fstrim 成功报告199.9GiB discard，但 Windows 可用空间未见增加。Windows Temp 检查最大目录约32MB，未找到可安全大幅回收对象；没有删除任务、运行材料、证据、用户媒体或可复用缓存，也没有关闭 WSL。

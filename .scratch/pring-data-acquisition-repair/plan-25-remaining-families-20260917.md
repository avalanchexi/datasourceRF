# #25 后续契约与完整 Worker 验证

本计划基于已读取的真实归档与当前源码，不是完成证明；无需新增网络请求。沿用已获用户确认的公开 seam：采集/EvidenceRepository/RunRepository 到 Worker、候选 CLI/ModelRepository/投影。完整 Worker 与阶段检索分别记账。

## 当前需要连接的入口

M1/M2 新契约阶段要求 money(include_month_on_month=False)，精确 month,m1,m1_yoy,m2,m2_yoy；Worker._refresh_context_sources 尚未传此参数。后续完整 Worker 红例必须先证明当前默认六字段导致新契约拒收，再仅对新不可变目录的显式 marker 选择四字段。旧默认六字段和必需四成员都保持。当前阶段通过不能称为自动刷新完成。

## SF 总量

已有真实 pbc_money.html 同页包含全部社融总量、组成、贷款与货币；无需再下载。2026-07 总量 stock_end=4632700 亿元，stock_yoy=7.4%，ytd_increment=222500 亿元。对应统计日 07-31；累计起点 01-01。原件 SHA256 933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef。

现有 sf_month 交付 inc_month（月增量）、inc_cumval（累计）、stk_endval（万亿元转亿元），但泛用 monthly_scalars 将累计也设为 month，这是新官方契约不可接受的语义。应以新显式交付契约保留官方共有必需两成员 stock_end/ytd_increment，正确累计期间；不原地改旧规范化证据，不虚构 TuShare 未交付的 stock_yoy。required_dimension_members 已明示 SF 不要求 stock_yoy；不可再缩减 stock_end 或 ytd_increment。

现有 pbc_social_financing 可解析该真实金融报告，scope 摄取须只写总量，其他组成保持。is_release_listing 尚仅支持 pbc_money 的人民银行目录，SF 应通过真实同页目录标题发现来扩展，并做按期次成功/未发/获取失败反例。

## GDP

当前 gdp() 保留四部门 nominal_ytd_level（year_to_quarter，从 01-01 起），请求的 gdp_yoy/pi_yoy/si_yoy/ti_yoy 口径仍 disputed，原件回执保留 rejected_fields。不能为过契约将这些字段改称当季或累计同比。新显式契约只开放四个已认可名义累计字段，并核整份规范化 accepted/rejected 响应。

官方契约当前同时列四个名义累计和四个实际当季同比，必需集合不会自动缩小为 TuShare 可交付部分。按指标有行则不做新鲜度回退的规则与维度未齐的原有质量规则应分别验证，不可为了合成 Worker completed 改必需维度。若需行为决策，应先呈现真实反例与具体差别。

NBS 历史 Q2 原件已存，见 verification-25-existing-gdp-20260917 相关记录；动态季度目录与新一期季度发现尚未接入（当前 prospective 仅 monthly），先以真实标题/期次验证再实现。

## 统一完整验证

完成必要契约后，再冻结当前完整输入、构建一个独立安装包，复用/生成相符的隔离候选材料，验证完整 Worker 的混合交付、双方缺失原失败分类、认证身份和投影/报告渠道。按所改接口做官方适配器/来源留痕变异证明。不能复用 45715b6 的旧 PPI 完整 Worker 通过来替当前代码背书。真实来源认证、候选准入、120 个中国交易日真实回放、显式激活与系统切换是后续独立实证门。

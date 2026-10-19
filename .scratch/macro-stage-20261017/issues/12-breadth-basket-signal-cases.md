# 12: 股市广度、商品篮子背离信号的单日汇总层用例

**What to build:** 为 B2、B4（股市广度背离）与 K2、K4（商品篮子背离）补单日汇总缝上的行为用例：另建 v0006 指标目录的单日汇总夹具（含 `CN_EQ_ABOVE_MA90`、分项贡献 `formula_version／sleeve` 维度），核心与宏观数据都放在 v0006 上。依据决定 57、review-fixes-20261019.md F13。

**Blocked by:** 10（激活后做，不阻塞激活）

**Status:** ready-for-agent

- [ ] 单日汇总测试：B2、B4、K2、K4 各按对照表映射到正确转换、成熟度与归组
- [ ] 两例冒烟通过

# 期货仓单单位换算核实（2026-10-07）

由 Codex（`codex --search exec -s read-only`）对照交易所官方规则与本地只读 SQLite 核实，用于预期表 O2「仓单综合读法」。原文如下（第 18 条后有一段重复输出，已截去）。

1. **结论：可采用 CF×40、TA×5、PP×5，CU/RB/RU/SP×1；SC 不宜强行采用固定吨桶系数。** 我建议把结果称为“仓单折算吨数”，以**各品种变化率和方向广度为主、七品种合计吨数为辅、SC 桶数单列**，因为统一单位并未统一经济含义；具体证据如下。

2. **CF、TA 的单位是本地写死的 `sheet`，不是动态读取上游单位。** 郑商所解析器读取日报仓库小计，但生成数据时直接赋值 `unit="sheet"`，标题校验也没有验证“单位：张”；这是一个可能漏检上游单位变化的地方。证据：[czce_warrants.py:125](/mnt/d/cursor/datasourceRF/src/pring_cycle/czce_warrants.py:125)、[czce_warrants.py:214](/mnt/d/cursor/datasourceRF/src/pring_cycle/czce_warrants.py:214)。

3. **PP、SC、CU、RB、RU、SP 的单位来自 TuShare 已返回的 `unit` 字段，本地仅翻译单位名称。** 映射为“吨→tonne、手→lot、桶→barrel”等，随后原样保留数量，并未乘以实物换算系数；目录允许混合单位也不意味着已经标准化。证据：[tushare_context.py:76](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:76)、[tushare_context.py:2279](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:2279)、[tushare_context.py:2327](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:2327)、[catalog.py:518](/mnt/d/cursor/datasourceRF/src/pring_cycle/catalog.py:518)。

4. **库内实际单位与问题所列一致，但 SC 的 `exchange` 字段实际存为 `SHFE`。** 我以 `mode=ro&immutable=1` 查询了 [SQLite 数据库](/home/tywin/.local/share/pring-cycle/pring-cycle.sqlite3) 的 `source_claim`，限定指标及 `measure=registered_receipts`：CF/TA=`sheet`、PP=`lot`、SC=`barrel`、CU/RB/RU/SP=`tonne`，各品种最新日期均为 **2026-09-30**，未发现其他单位。查询口径和既有调查亦可核对：[confirmation-indicator-coverage.md:33](/mnt/d/cursor/datasourceRF/docs/research/confirmation-indicator-coverage.md:33)、[同文件:81](/mnt/d/cursor/datasourceRF/docs/research/confirmation-indicator-coverage.md:81)。

5. **CF：1 张仓单按 40 吨折算，但不能声称每张实物恰好重 40 吨。** 《棉花期货业务细则》第三条为“5吨/手（公定重量）”，第十二条规定一个交割单位对应八手，实物按棉包数量及允许偏差组织，因此名义折算为 8×5=40 吨。证据：[官方业务细则](https://www.czce.com.cn/cn/flfg/zcjywgz/pzxz/webinfo/2024/02/1708568084281851.htm)、[官方年报第33页明确列示棉花40吨/张](https://www.czce.com.cn/cn/rootimages/2014/07/14/1405082903702590.pdf)。

6. **TA：1 张仓单对应 5 吨。** 《PTA期货业务细则》第十二条规定“交割单位为5吨”，官方仓单统计说明也明确列示 PTA 每张对应5吨；项目取完税与保税仓单之和，不包含有效预报。证据：[官方业务细则](https://www.czce.com.cn/cn/uploadfile/2024/02/07/20240207154327860.pdf)、[官方统计说明第33页](https://www.czce.com.cn/cn/rootimages/2014/07/14/1405082903702590.pdf)、[czce_warrants.py:69](/mnt/d/cursor/datasourceRF/src/pring_cycle/czce_warrants.py:69)。

7. **PP：上游1手对应5吨。** 大商所《聚丙烯期货业务细则》第八条原文为“聚丙烯期货合约的交易单位为5吨/手”，因此已确认单位为 `lot` 的仓单数量乘5。证据：[大商所官方业务细则](https://www.dce.com.cn/dalianshangpin/fgfz/6142914/6142926/6146588/大连商品交易所聚丙烯期货业务细则（根据2024年11月1日〔2024〕102号文件修改）.pdf)。

8. **CU：项目输入已经是吨，系数为1，不能再乘5或25。** 官方合约附件分别规定交易单位5吨/手、每一仓单25吨，后者描述仓单对应的交割批量，并不是当前数据库数值的单位。证据：[官方合约附件](https://www.shfe.com.cn/products/futures/metal/nonferrousmetal/cu_f/appendix/)、[库内单位调查:81](/mnt/d/cursor/datasourceRF/docs/research/confirmation-indicator-coverage.md:81)。

9. **RB：项目输入已经是吨，系数为1，但属于理论计重口径。** 官方合约附件明确“螺纹钢交割以理论计重方式计量”，因此它与过磅实重仍有口径区别。证据：[官方合约附件第（6）项](https://www.shfe.com.cn/products/futures/metal/ferrousandpreciousmetal/rb_f/appendix/202206/t20220621_798838.html)、[库内单位调查:81](/mnt/d/cursor/datasourceRF/docs/research/confirmation-indicator-coverage.md:81)。

10. **RU：项目输入已经是吨，系数为1。** 官方业务细则第二十一条规定每一标准仓单10吨，这不能成为对已经按吨发布的数据再乘10的理由。证据：[官方业务细则](https://www.shfe.cn/regulation/exchangerules/historicalversion/202409/t20240903_802264.html)、[库内单位调查:81](/mnt/d/cursor/datasourceRF/docs/research/confirmation-indicator-coverage.md:81)。

11. **SP：项目输入已经是吨，系数为1，但具体是风干重。** 官方业务细则第十八条规定按实测风干重计重，第十九条规定每一标准仓单重量为20吨，不能把当前吨数再乘20。证据：[官方业务细则](https://www.shfe.cn/regulation/exchangerules/productrules/202512/t20251231_829972.html)、[库内单位调查:81](/mnt/d/cursor/datasourceRF/docs/research/confirmation-indicator-coverage.md:81)。

12. **SC：仅凭现有桶数，不能确定性得到吨数，已查规则没有给出通用固定吨桶系数。** 能源中心《交割细则》第一百五十二条按“原油净体积桶数”计量，而可交割油种规定的是不同 API 品质范围，例如阿曼≥30、穆尔班≥35，并非所有仓单具有同一个密度。证据：[官方交割细则](https://www.shfe.cn/regulation/ineregulation/businessmethods/delivery/202606/t20260626_832297.html)、[官方可交割油种及品质表](https://www.ine.com.cn/upload/20240325/1711331212000.pdf)。

13. **历史判断：未发现上述换算系数在2025年至2026-10-07间调整，但不能把本次检索当成“全期绝无变化”的完整证明。** 规则确实修订过，例如 RB 的版本自2025-04-14实施、INE《交割细则》现行版本自2026-07-25实施；部分郑商所、大商所修订附件访问失败，未完成全部版本逐条对照。证据：[RB历史版本](https://www.shfe.cn/regulation/exchangerules/historicalversion/202503/t20250314_824804.html)、[INE现行版本及修订沿革](https://www.shfe.cn/regulation/ineregulation/businessmethods/delivery/202606/t20260626_832297.html)。

14. **目前没有证据要求这些系数按2025/2026年份机械分段，但应保留按生效日期版本化的能力。** 我的建议是记录“品种、输入单位、系数、重量口径、生效区间、官方依据”，只有相关条款实际改变才新增区间；项目2026年9月切换 CF/TA 数据源属于另一类变化，旧 TuShare 声明不能与官方声明重复相加。证据：[ADR-0032:9](/mnt/d/cursor/datasourceRF/docs/adr/0032-czce-warrants-from-exchange-daily.md:9)、[ADR-0032:21](/mnt/d/cursor/datasourceRF/docs/adr/0032-czce-warrants-from-exchange-daily.md:21)。

15. **SC有三种处理，我优先选择“桶数单列，同时参加无量纲综合读法”。** 保持桶数最忠实，但不能进入吨数合计；采用官方公布的某油种品质作估算，例如把阿曼 API 下限30当情景值，会引入油种、批次及密度假设，且下限不能冒充实际平均值；完全排除则简洁，但会损失原油覆盖，应明确合计只有七品种。参考：[官方油种品质表](https://www.ine.com.cn/upload/20240325/1711331212000.pdf)、[官方标准合约的API32基准品质](https://www.ine.com.cn/products/futures/energyandchemical/sc_f/standard_sc_f/202312/t20231205_802540.html)。

16. **跨品种吨数相加具有算术意义，经济解释却很有限。** 一吨铜和一吨纸浆不代表相等的经济规模或供需压力，大吨位品种会自然主导合计变化，而且公定重量、理论重量、风干重也并非同一种实重；仓单注册、注销还不等于全社会库存增减。项目本身已明确仓单不是工业总库存：[context_projection.py:518](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:518)。

17. **建议主读法采用固定窗口的品种变化率中位数，以及“增加／持平／减少”的方向广度。** 固定系数在同品种变化率中会抵消，因此 SC 可以直接用桶数参加八品种广度，七品种折算吨数变化仅作为辅助；如需加权，优先采用预先冻结的行业权重或基期价值权重，避免当前吨位或价格变化悄悄改变权重。计算必须对齐日期、避免重复声明、明确有效品种覆盖，缺失及零基数不能当作零变化，相关缺口见 [confirmation-indicator-coverage.md:81](/mnt/d/cursor/datasourceRF/docs/research/confirmation-indicator-coverage.md:81)。

18. **本次全程只读：未修改文件、未运行测试、未调用 TuShare。** SQLite 查询前确认没有 WAL/SHM 文件，连接启用只读、`query_only`，临时排序限于内存。

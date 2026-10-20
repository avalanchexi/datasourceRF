Status: reviewed-with-open-boundary
Axis: Spec
Date: 2026-09-10
Scope: 153-155 Q1 test increment and remaining closure conditions

八文件当前 SHA 均匹配冻结 155；七生产文件仍与冻结 147 一致。仅审测试增量及其关闭条件，未执行测试、安装或修改源码。

**测试增量的确定缺陷 0；仍有 1 项需要反例验证的实质边界。**

已核对：[工程边界 L78–83](capacity-q1-implementation-boundary.md#L78)要求错字段/错期、表列身份、制品完整性、新 vintage 和直接追加防绕过。[测试 L6449–6560](../../tests/models/test_candidate_admission.py#L6449)先合法公开追加，再缺/错/混入收据、缺坏 raw/normalized、替换为哈希自洽的错值规范收据，并核原声明集合未被覆盖。[L6576–6656](../../tests/models/test_candidate_admission.py#L6576)先合法准入，再逐项变换表格；独立累计列先证明 parser 保留实际列值，随后仅拒绝别名许可，符合 [规格 L82](capacity-q1-implementation-boundary.md#L82)，没有把页面一概判为非法。

[L6066–6172](../../tests/models/test_candidate_admission.py#L6066)分别检查三制品损坏/缺失的组件回放结果及实际采用集合，正确区分共享 raw/normalized 影响两目录、候选 mapping 只影响候选，并显式拒绝跨目录 ytd 借用。[L6175–6303](../../tests/models/test_candidate_admission.py#L6175)先验证两个合法发布 cutoff，再损坏后发 raw/normalized，核旧 cutoff 不变、最新不能退回旧值。

**待验证：后发 mapping 附件损坏是否污染旧 cutoff。** [规格 L81](capacity-q1-implementation-boundary.md#L81)要求“旧 PUBLIC/SYSTEM cutoff 重现旧版本”，[L80](capacity-q1-implementation-boundary.md#L80)将映射附件纳入完整性边界；但新晚修订测试只参数化 raw/normalized。[source_contract_review.py L427–431](../../src/pring_cycle/source_contract_review.py#L427)在判断目标 raw 前读取全部审查附件，故同一原入场包许可两 vintage 时，后发 mapping 损坏会先令整个查找失败，旧 claim 也可能失去资格。这是静态控制流推断，尚未取得该反例运行结果。建议同一晚修订正例增加 mapping 损坏/缺失，只改变后发附件，核旧 PUBLIC/SYSTEM cutoff 保持旧值、最新明确不可用；解决前不关闭 Q1 软件矩阵。

已读取真实日志及终态：[153](verification-capacity-replay-153.txt)6 通过、40.62 秒；[154](verification-capacity-ingress-154.txt)16 通过、130.07 秒；[155](verification-capacity-revision-155.txt)8 通过、57.67 秒，[155 终态](verification-capacity-terminal-155.json)前验/测试/后验均退出 0。新增四项字段/schema/rule 反例尚待最终关联运行；各批不能累加为同版全套。真实来源认证、历史首发、完整候选和固定 120 日产品验收仍独立未完成。

| 文件 | SHA-256 |
|---|---|
| evidence.py | `5172343e432904c449e060b9c093b50ef33e76c85425c0912e95b4e06f740294` |
| official_context.py | `12dc0b7a78c80f407f4e7971ac0f1ac9c100ba224df6f9913c4a37a410948947` |
| search_evidence.py | `beea9d67529a9b9dd368980c99aa5b49e584561ec50075ab92e78ce5dd66fa46` |
| context_projection.py | `8ccfbc5b1fd1f4d1782c4566b97168f8576f0d810c0de63a70a46869d0e6efaa` |
| model_evaluation.py | `2029a89c4e9ac24ac08ca39f3adce890b1e33ae31af1d1d2d54764b77304e113` |
| source_contract_review.py | `b71faa479efc39538c82fbe300475aa5b935b96ae2c48caae5804f90fce55fce` |
| candidate_admission.py | `f6677cbd75d982faeca31ef37839858532593bb6f0a4828aed4ea084efc27a49` |
| test_candidate_admission.py | `c5dc2ce2ace6eefbffdb00c3fa877deee4227fe950e7cc5da490e8e5d2b361ed` |

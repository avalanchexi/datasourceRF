Status: static-review-passed
Axis: Spec
Date: 2026-09-10
Scope: 144-147 Q1 consumer and admission increment

基点与 HEAD 均为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，提交列表为空。核实工作区八文件差异非空；仅审本轮收据匹配的显式目录参数、已存声明合同复验、映射准入预检及相关 fixture/测试，排除此前修复。比较命令：`git diff 99c495a217b66d4bca9d6ceae4688ee69d4382bb -- src/pring_cycle/evidence.py src/pring_cycle/official_context.py src/pring_cycle/search_evidence.py src/pring_cycle/context_projection.py src/pring_cycle/model_evaluation.py src/pring_cycle/source_contract_review.py src/pring_cycle/candidate_admission.py tests/models/test_candidate_admission.py`。

**确定实现问题 0；未发现范围扩张。**

- [工程边界 L57](capacity-q1-implementation-boundary.md#L57)要求“消费者复用同一个校验，不信任写入时曾通过”。[official_context.py L350–361](../../src/pring_cycle/official_context.py#L350)对 Q1 ytd 重验合同；[evidence.py L426–455](../../src/pring_cycle/evidence.py#L426)从真实存储声明读取身份、核对目标 definition_version，再调用写入前同一校验。检索 [L130](../../src/pring_cycle/search_evidence.py#L130)、上下文 [L1440](../../src/pring_cycle/context_projection.py#L1440)、回放 [L1186](../../src/pring_cycle/model_evaluation.py#L1186)均传入各自目标版本。未发现跨目录 ytd 声明获得该资格的路径。
- [L55](capacity-q1-implementation-boundary.md#L55)要求从“原入场模型”取绑定，不能扩张同目录许可。[source_contract_review.py L395–456](../../src/pring_cycle/source_contract_review.py#L395)仍沿 registered catalog 的 admitted_by_model_id 读取原包；后续模型自身附加 review 不参与此查找。
- [L54](capacity-q1-implementation-boundary.md#L54)要求候选入场专门验证映射附件。[candidate_admission.py L68](../../src/pring_cycle/candidate_admission.py#L68)在持久创建候选前调用预检；[source_contract_review.py L490–550](../../src/pring_cycle/source_contract_review.py#L490)检查双 assessment、定义/包绑定、规则/parser、原件及源/目标字段、期间、单位、真实格值，不只认 accepted。缺映射旧包仍不获得 Q1 别名许可。

新测试核对真实选中/采用 claim 集合，并分别损坏候选侧附件；回放明确仅为单日组件测试。完整 raw/normalized 损坏、哈希自洽错语义、缺成员、新 vintage、未知 PUBLIC、晚修订，以及同目录后续 review 不扩权和跨目录借用的专门反例仍待覆盖，不能据静态结论关闭整项 Q1。synthetic 审查不等于真实认证。

交付前只读核实 [147 运行日志](verification-capacity-admission-green-147.txt)及[终态](verification-capacity-terminal-147.json)：5 通过、1 失败，33.34 秒，退出 1、后验 0。已知测试准备问题 1：错值已由新校验拒绝为 `certification_source_mapping_invalid`，CLI 正常转为 SystemExit(2)，但 [测试 L5826](../../tests/models/test_candidate_admission.py#L5826)仍预期 ValueError。需改断言退出码和 stderr 后重验，不能称 147 全绿。后续 148 修改未纳入本报告。本次未执行测试、安装或修改源码。

八文件当前 SHA 均匹配 `verification-capacity-inputs-147.json`：

| 文件 | SHA-256 |
|---|---|
| evidence.py | `5172343e432904c449e060b9c093b50ef33e76c85425c0912e95b4e06f740294` |
| official_context.py | `12dc0b7a78c80f407f4e7971ac0f1ac9c100ba224df6f9913c4a37a410948947` |
| search_evidence.py | `beea9d67529a9b9dd368980c99aa5b49e584561ec50075ab92e78ce5dd66fa46` |
| context_projection.py | `8ccfbc5b1fd1f4d1782c4566b97168f8576f0d810c0de63a70a46869d0e6efaa` |
| model_evaluation.py | `2029a89c4e9ac24ac08ca39f3adce890b1e33ae31af1d1d2d54764b77304e113` |
| source_contract_review.py | `b71faa479efc39538c82fbe300475aa5b935b96ae2c48caae5804f90fce55fce` |
| candidate_admission.py | `f6677cbd75d982faeca31ef37839858532593bb6f0a4828aed4ea084efc27a49` |
| test_candidate_admission.py | `d519ea6e09852cb5a529773d2e87f0d84282fde3057bd7eddb5725915f1a32a9` |

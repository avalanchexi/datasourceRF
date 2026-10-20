Status: static-review-passed
Axis: Spec
Date: 2026-09-10
Scope: 148-151 test increment only

**新增确定问题 0。** 仅审新增/调整的 Q1 测试；七个生产文件逐字节仍匹配冻结 147，不重复扩大生产审查。八文件实际 SHA 均匹配冻结 151。

- [工程边界 L54](capacity-q1-implementation-boundary.md#L54)要求“附件缺定义、错 raw、错 parser、错源格或错误目标身份均拒绝”。[测试 L5806–5873](../../tests/models/test_candidate_admission.py#L5806)覆盖 16 种错误，每项先完成合法公开准入，再只改变一个映射条件并重新计算外围哈希；断言 CLI 退出 2、确切错误和候选版本集合不变。其“哈希自洽”指外围 JSON/包链重新保存，不表示故意写成零的原件/依据哈希有对应合法制品。
- [L80](capacity-q1-implementation-boundary.md#L80)要求“合法入库后……分别验证检索不补齐、上下文 source_failed”。[测试 L6034–6059](../../tests/models/test_candidate_admission.py#L6034)分别损坏 mapping/raw/normalized，核对检索及模型实际采用集合；原件或规范化损坏时三声明全部退出采用，映射损坏时 ytd 退出；历史证据身份仍保留。PUBLIC 组件回放目前仍只测试映射附件损坏，不应称三种制品均已覆盖回放。
- [L55](capacity-q1-implementation-boundary.md#L55)要求“旧目录接受集合不变”，[L81](capacity-q1-implementation-boundary.md#L81)要求同 URL 新 raw 不继承映射、无可靠新时间 PUBLIC 保持未知。[测试 L6139–6266](../../tests/models/test_candidate_admission.py#L6139)验证原目录拒绝新字节、同目录后续模型新 review 不扩权、新目录独立映射接受，并保留旧声明。合成修订明确不冒充真实官方修订。

151 将历史定向检索的 SYSTEM/PUBLIC 都断言缺口，同时单独核对直接 SYSTEM 可见及采用，符合既有 [TargetBoundEvidenceRepository L595–599](../../src/pring_cycle/context_projection.py#L595) 的目标日 PUBLIC 上界；不是放宽生产规则。完整缺成员、制品缺失、错语义规范化及晚修订跨 cutoff 矩阵仍不由这些测试替代。

只读核实真实运行记录：[148](verification-capacity-terminal-148.json)路径错误，0 执行、退出 4；[149](verification-capacity-matrix-149.txt)30 通过、120.88 秒，退出/后验 0；[150](verification-capacity-vintage-150.txt)1 失败、17.79 秒，属上述历史目标预期错误；[151](verification-capacity-vintage-151.txt)1 通过、15.06 秒，[终态](verification-capacity-terminal-151.json)退出/后验 0，结束于 `2026-09-10T02:21:55.4552097Z`。不累加批次数、不据此关闭整项 Q1、真实认证或 120 日验收。本审查没有执行测试、安装或修改源码。

| 文件 | SHA-256 |
|---|---|
| evidence.py | `5172343e432904c449e060b9c093b50ef33e76c85425c0912e95b4e06f740294` |
| official_context.py | `12dc0b7a78c80f407f4e7971ac0f1ac9c100ba224df6f9913c4a37a410948947` |
| search_evidence.py | `beea9d67529a9b9dd368980c99aa5b49e584561ec50075ab92e78ce5dd66fa46` |
| context_projection.py | `8ccfbc5b1fd1f4d1782c4566b97168f8576f0d810c0de63a70a46869d0e6efaa` |
| model_evaluation.py | `2029a89c4e9ac24ac08ca39f3adce890b1e33ae31af1d1d2d54764b77304e113` |
| source_contract_review.py | `b71faa479efc39538c82fbe300475aa5b935b96ae2c48caae5804f90fce55fce` |
| candidate_admission.py | `f6677cbd75d982faeca31ef37839858532593bb6f0a4828aed4ea084efc27a49` |
| test_candidate_admission.py | `6538b8479de072f037aa3f6faef37a347add5c075dfb55eb2f4c4c065dd12023` |

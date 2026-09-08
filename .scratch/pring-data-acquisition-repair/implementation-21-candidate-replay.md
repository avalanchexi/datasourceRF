# PUBLIC 候选字段与回放明细

2026-09-09，固定基点 `0c33710842f3b68e92ed207c0a94ec472424a811`。票19/21的代码切片已通过342项关联测试，0失败，550.74秒，包含34项新增候选用例；不是正式来源认证、新完整实际候选、真实120日回放或切换验收。

## 行为与保存契约

- 逐日输出保留三核心稳定状态、候选方向、实际持续天数、模型版本对应的显示天数及确认阈值。v0001继续旧显示语义；v0002为实际候选天数。第8日确认后候选归零，中断重新累计，非典型组合保持空阶段。
- 候选字段沿用每天的PUBLIC选源与修订切点。测量前的输入只作预热，不把预热日放进可见输出。真实历史时间和来源认证未由合成用例授予。
- 校准文档绑定模型/清单hash、候选规则、PUBLIC模式、请求范围、输入证据指纹、实际日期日历及逐资产字段。回放文档保存两侧文档和逐日逐字段差异，允许合理非零差异。
- 规范UTF-8 JSON的SHA256明细保存在追加式SQLite `model_evaluation_output` 表，与校准/回放引用在同一连接事务写入；更新/删除触发器拒绝改写。此为结构化计算结果，不是来源原始文件CAS。符合ADR0006/0007/0012；旧记录缺引用明确为`not_recorded`，两个候选差异计数为null，不填0。
- 读取核对存档hash、模型/规则、范围、三资产成员和字段、候选计数/阶段、日历及差异摘要。保存结果不因后续补证而覆盖；公开`replay_matches_current_evidence`重新计算完整输出hash，已有差异数量相同也不足以通过。hardened激活调用此检查，校准机验也核验存档明细。
- 新hardened且duration-v0002的回放不能缺候选明细通过。旧legacy手工摘要入口保留，但无明细记录不能通过完整证据匹配检查；正式新目录准入仍强制v0002与已有来源合同。

## 可查询接口

- CLI：`model-replay-show --replay-id ID --json`；`model-acceptance-show --model MODEL --result-hash HASH --json`，沿用既有`--runtime-root`参数。
- GET：`/api/v1/model-replays/{replay_id}`；`/api/v1/models/{model_version_id}/acceptances/{result_hash}`。查询读取保存文档，不改发布历史或当前指针。
- Alembic 0020为旧0019运行库追加明细表和三项可空列，保持冻结初始schema；再次迁移不改变旧失败记录。CLI保留原请求的认证交集范围，末日缺数据时保存失败原因及实际日行，不通过缩短终日掩盖缺口。

## 验证进度与失败记录

- [历史候选RED](verification-candidate-replay-red-01.txt)证明字段缺失；[27项领域与历史回归](verification-candidate-replay-green-02.txt)包括7天、第8天确认、中断、反向及修订。
- [校准RED](verification-candidate-calibration-red-01.txt)与[GREEN](verification-candidate-calibration-green-01.txt)证明保存/读回；[CLI RED](verification-candidate-persist-red-01.txt)与[GREEN](verification-candidate-persist-green-01.txt)证明两规则差异和CLI/API读回。
- [非法输入指纹RED](verification-candidate-integrity-red-02.txt)与[GREEN](verification-candidate-integrity-green-01.txt)。前一次[red-01](verification-candidate-integrity-red-01.txt)是测试未创建基线模型的设置错误，不能充当缺陷证明。
- [证据失配RED](verification-candidate-current-red-01.txt)与[GREEN](verification-candidate-current-green-01.txt)：同价格的较晚取得版本在原历史cutoff可见，阶段及各差异数量不变，完整输出hash改变，旧存档保留且机验拒收。
- [读写契约RED](verification-candidate-read-contract-red-01.txt)记录缺空阶段字段、布尔天数和缺校准查询入口；修复后[30项通过](verification-candidate-read-contract-green-01.txt)。
- 第一轮模型关联为[66通过/2失败](verification-candidate-models-01.txt)：新明细门错误影响旧duration-v0001手工摘要测试，现仅新hardened v0002禁止无明细通过，旧摘要仍不具备完整证据机验资格。修复后两项包含在最终342通过中。
- 双轴初审指出旧库缺迁移和非精确请求区间失败记录不能保存。[两个RED](verification-candidate-review-red-01.txt)已复现，[两个GREEN](verification-candidate-review-green-01.txt)通过。静态复审两轴剩余均0；未用静态复审代替测试。
- [最终关联342通过](verification-candidate-associated-01.txt)覆盖全部models、趋势、候选投影、核心采集、Worker、原子投影、两组CLI及投影API。mypy检查89个文件通过，Ruff/格式9文件通过，88个安装Python源与工作区匹配；见[检查点](verification-candidate/checkpoint.json)。这不是全项目最终门。

## 尚未完成

本切片没有取得官方样本或认证；没有创建真实完整候选、运行真实120中国交易日验收、取得合格AI输出或切换。新目录active Worker完整纵向、normalized消费完整性、完整P1/P2来源与上下文逐日证据验收仍开放。全项目最终质量/回归/性能门亦未关闭。

后续先验证[上下文逐日快照缺口](context-replay-snapshot-boundary.md)：当前只返回上下文差异数量，尚无对应输入快照保存。该文是静态定位，不是已经复现或修复的结论。

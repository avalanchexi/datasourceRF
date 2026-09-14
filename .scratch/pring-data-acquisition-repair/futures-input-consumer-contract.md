# 票11输入接口与票12消费边界

当前软件验证与审查以[实施记录](implementation-11-futures-inputs.md)最新终态为准；本页不是来源认证或整票验收。

## 先获取原件，再绑定已审发布时间

`TushareContextAdapter.acquire_futures_inputs(paths, products=..., start_date=..., end_date=...)` 获取真实月份身份、各交易所日历及同合约结算/前结算，返回 `FuturesInputAcquisition.acquisition_ids`。原响应、请求参数及校验时间通过 `AcquisitionRepository` 读取。没有可靠发布时间时，PUBLIC为空，SYSTEM只从校验完成后可查。

完成实际时间依据的审查后，调用公开 `pring_cycle.futures_inputs.bind_futures_input_evidence(paths, acquisition_ids=original_acquisition_ids, evidence_hash=packet_hash)`。传入首次采集返回的TuShare原件获取ID集合；函数另存已审证据包及新的标准化输入版本，不调用transport，不覆盖原获取或标准化材料。后续补证仍引用原始TuShare获取ID，不把先前的审查包获取ID当成TuShare响应。新版本SYSTEM从新审查包校验完成后可用，旧截止查询仍读原版本。

已审包的publication按 `api_name + parameters + raw_hash` 精确绑定，还可用 `contract_code`、`business_date`缩小范围。包引用证明原件及接受审查，审查的subject_hash绑定包内容。不能先抓一次做审查、再假设下一次联网响应仍有同一哈希；真实响应的request_id也属于原件。原采集接口的 `evidence_hash` 参数只适用于证明恰好绑定该次实际响应的场景，不替代后审关联。

## 查询与采用

`select_futures_inputs(paths, products=..., business_date=..., mode=AsOfMode.PUBLIC或SYSTEM, as_of=带时区时间)` 返回 `contracts`、`calendar`、`settlements`、`sessions`、`contract_failures` 和 `missing`。

- 合约保留真实月份、来源代码（含CZCE短码）、上市/最后交易日、单位和乘数，排除目标日尚未上市或已到期的身份。
- 结算同时保留同合约 `settle/pre_settle`，缺值显式不可用；不使用close补值。
- 品种时段以品种、交易所和所属交易日为身份；不由当前交易所通用时刻猜历史夜盘。
- PUBLIC先要求全部采用材料已公开，再按事实自身来源的 `source_public_available_at` 选择版本；复合 `public_available_at` 仍是全部父项的保守可见门，日期精度从下一上海本地日开始。SYSTEM同样先要求全部采用材料已校验，再按事实自身原件版本顺序选择。给旧原件补审时间或较晚更新合约身份，都不会把旧价格升为新的上游修订；证明包本身提供的时段按其版本顺序选择。最新同来源公开时点的矛盾事实形成冲突，不按采集顺序裁决；更晚版本可继续选择。
- 每个采用事实关联实际获取ID、raw_hashes、证明哈希及其时间。查询只核本次范围、时点采用的原件；损坏材料形成明确缺口，恢复原字节后可重新查询。

票11列出目标日至本次可见最晚到期日之间的日历缺失/未知。票12必须检查所选合约所需的具体区间，不把无关远月的缺日一概设为近月选择失败，也不能把少一日误计成严格10/11日边界。

## 保留的验收责任

票12负责按交易时段开始前可知输入冻结选约、处理当日新公告下一交易日生效、同合约收益、每日恢复权重、2026-03-06收盘1000基点及两项注册合同。票11不产生篮子值、模型激活或来源认证。真实PP发布方、历史身份/日历/时段及PUBLIC证据与许可按原票继续补齐；合成测试的已审包不构成真实认证。

## 票12的SYSTEM消费扩充

`select_futures_inputs` 新增可选 `system_as_of`，用于同时限定历史PUBLIC知识和本机取得时间：例如以PUBLIC的T夜盘前cutoff选择事件，但仅允许在指定SYSTEM截止前已经校验的原件与审查包。默认未提供该参数的既有PUBLIC/SYSTEM语义保持原样。新上限同时约束获取收据及事实所用全部父项，不能让后来补审的材料提前进入旧系统快照。

票12的 `select_commodity_contracts`、`calculate_commodity_returns` 和 `calculate_commodity_basket` 均要求显式传入 `mode`，没有默认值。

`contract_failures` 是当前点时不能可靠采用的合约身份列表，成员含 `product`、`contract_code`。冲突或损坏的近月身份不能从候选集合静默消失后改选远月。审查规范化制品损坏时，只从完整原件恢复用于隔离的身份与版本顺序；重建项仍无效。若原件也无法确定范围，保守返回受影响产品的未知身份缺口。完整后续版本可以接替；无关结算缺失或超出必需区间的日历缺日仍由相应消费者判定。

## 商品不可变结果与注册消费

`persist_commodity_basket(paths, business_date=..., as_of=..., mode=..., definition_version=...)` 只接受新的注册目录。完整结果追加独立 `commodity_basket` 获取收据及8个标量声明（篮子加七袖套贡献），返回 `claim_ids`、`result_hash` 与空 `missing`；计算或目标输出缺失时返回缺口和空ID集合，不生成空声明。输入原收据不改写，结果保留固定基点、每日选择、价格、公式、权重及完整父项。

写入前核对结果原件、父项和精确计算，要求完整非空且确有目标日输出，不能把上一交易日的值标为休市日新值；候选读取及PUBLIC回放再次核对原件、父项及调用方点时。等值价格格式和郑商所合法简称重送不会改变旧结果身份；真实修订采用新父项并追加新结果。未知PUBLIC时间的系统结果不提前进入PUBLIC。上述接口不会授予真实来源认证或激活模型。实际验证、独立提交范围和待办以[票12记录](implementation-12-commodity-basket.md)为准。

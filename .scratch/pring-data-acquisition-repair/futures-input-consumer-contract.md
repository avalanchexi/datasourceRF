# 票11输入接口与票12消费边界

当前软件验证与审查以[实施记录](implementation-11-futures-inputs.md)最新终态为准；本页不是来源认证或整票验收。

## 先获取原件，再绑定已审发布时间

`TushareContextAdapter.acquire_futures_inputs(paths, products=..., start_date=..., end_date=...)` 获取真实月份身份、各交易所日历及同合约结算/前结算，返回 `FuturesInputAcquisition.acquisition_ids`。原响应、请求参数及校验时间通过 `AcquisitionRepository` 读取。没有可靠发布时间时，PUBLIC为空，SYSTEM只从校验完成后可查。

完成实际时间依据的审查后，调用公开 `pring_cycle.futures_inputs.bind_futures_input_evidence(paths, acquisition_ids=original_acquisition_ids, evidence_hash=packet_hash)`。传入首次采集返回的TuShare原件获取ID集合；函数另存已审证据包及新的标准化输入版本，不调用transport，不覆盖原获取或标准化材料。后续补证仍引用原始TuShare获取ID，不把先前的审查包获取ID当成TuShare响应。新版本SYSTEM从新审查包校验完成后可用，旧截止查询仍读原版本。

已审包的publication按 `api_name + parameters + raw_hash` 精确绑定，还可用 `contract_code`、`business_date`缩小范围。包引用证明原件及接受审查，审查的subject_hash绑定包内容。不能先抓一次做审查、再假设下一次联网响应仍有同一哈希；真实响应的request_id也属于原件。原采集接口的 `evidence_hash` 参数只适用于证明恰好绑定该次实际响应的场景，不替代后审关联。

## 查询与采用

`select_futures_inputs(paths, products=..., business_date=..., mode=AsOfMode.PUBLIC或SYSTEM, as_of=带时区时间)` 返回 `contracts`、`calendar`、`settlements`、`sessions` 和 `missing`。

- 合约保留真实月份、来源代码（含CZCE短码）、上市/最后交易日、单位和乘数，排除目标日尚未上市或已到期的身份。
- 结算同时保留同合约 `settle/pre_settle`，缺值显式不可用；不使用close补值。
- 品种时段以品种、交易所和所属交易日为身份；不由当前交易所通用时刻猜历史夜盘。
- PUBLIC先要求全部采用材料已公开，再按事实自身来源的 `source_public_available_at` 选择版本；复合 `public_available_at` 仍是全部父项的保守可见门，日期精度从下一上海本地日开始。SYSTEM同样先要求全部采用材料已校验，再按事实自身原件版本顺序选择。给旧原件补审时间或较晚更新合约身份，都不会把旧价格升为新的上游修订；证明包本身提供的时段按其版本顺序选择。最新同来源公开时点的矛盾事实形成冲突，不按采集顺序裁决；更晚版本可继续选择。
- 每个采用事实关联实际获取ID、raw_hashes、证明哈希及其时间。查询只核本次范围、时点采用的原件；损坏材料形成明确缺口，恢复原字节后可重新查询。

票11列出目标日至本次可见最晚到期日之间的日历缺失/未知。票12必须检查所选合约所需的具体区间，不把无关远月的缺日一概设为近月选择失败，也不能把少一日误计成严格10/11日边界。

## 保留的验收责任

票12负责按交易时段开始前可知输入冻结选约、处理当日新公告下一交易日生效、同合约收益、每日恢复权重、2026-03-06收盘1000基点及两项注册合同。票11不产生篮子值、模型激活或来源认证。真实PP发布方、历史身份/日历/时段及PUBLIC证据与许可按原票继续补齐；合成测试的已审包不构成真实认证。

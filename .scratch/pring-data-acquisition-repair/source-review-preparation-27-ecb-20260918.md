# ECB 真实来源认证材料准备

本记录为真实原件的六项审查准备，不是来源认证决定、候选准入、回放通过或激活。仅重读已归档原件，不联网、不改应用数据库、声明或认证状态。用户已选择独立 ECB 参考交叉口径，不再请求相同选择。

## 原件与身份

逐件复核了 2026-09-17 取得的 ECB 历史 ZIP、参考汇率介绍页及使用条款，长度与 SHA256 均匹配原回执；解压 CSV 的哈希也一致。可复现脚本为 `prepare-27-ecb-evidence-map-20260918.py`，完整结果为 `verification-27-ecb-real-evidence-map-20260918.json`。

- 历史 ZIP：`56a389450a063c0637462db6e33575b45048e181a8071adc9cef2438c97c9e51`，639,398 字节。
- CSV：`9ee21621a088d3ad15247846e98d27bf4ac19c863e165f6817eff0e6e87770ae`，1,921,736 字节。
- [官方参考汇率介绍](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)：`5fb65626d74541d498ec86c79787a95b5c6fc89d4fa1077df39e7d766302e873`。
- [使用条款](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html)：`be53aefb3632a9571e4763ca9ff267d4f3da5c097ea665d77feac83a564d5c85`；这里说明的是归档版本，不声称重新核实当前网页。

## 六项准备结论

| 维度 | 原件支持与使用边界 | 正式包尚需绑定 |
|---|---|---|
| semantics | 同日 ECB 欧元参考价的 CNY 腿除以 USD 腿；独立 `CN_USDCNY_ECB_REFERENCE_CROSS`，人民币/美元。不是 CNH 即期或中国 16:30 收盘，旧 FXCM/TMA 历史不拼接。 | 精确新定义哈希、不可变模型 manifest |
| fields | 原 ZIP 唯一 CSV 成员，Date/CNY/USD；双腿正有限数。同日相除使用34位十进制有效数字与ROUND_HALF_EVEN，保留双腿/公式/原件血缘。 | 实际应用导入回执、归一化原件与契约版本 |
| history | 5,496 个有效双腿日期，2005-04-01 至2026-09-17。缺腿不补值，跨中国/ECB日历不伪造同日样本。 | 具体模型所需窗口及按目标日选值结果 |
| time | 统计日期及常规日程不能证明历史各版本首次公开时间；release_at/public_available_at保持NULL。SYSTEM以应用实际取得并校验时刻为准，不能把研究下载时刻倒写成应用可用时刻。 | 实际应用时间回执、新模型dual-cutoff-v0003、历史不可见反例 |
| permissions | 归档条款支持直接信息的使用，要求准确、署名及说明修改；本项目标注ECB来源和交叉计算。署名作者文稿的例外与本数据文件区别处理。 | 真实包的用途描述与署名/计算说明制品 |
| usage | P2宏观背景；不据此描述离岸压力、在岸/离岸价差或16:30收盘。未通过其他认证与质量条件前仍不进入模型。 | 实际投影/报告中的身份与来源说明 |

## 120 中国交易日与 ECB 日期的实测区别

以已有真实 TuShare 中国交易日历原件 `2c8576c3d87cca2973053122683cd3ee48c1b29b3524f500179e123d40785705` 比较固定区间2026-03-09至08-28：

- 中国交易日为120个，同区间ECB参考日期为122个。
- 119个中国交易日具有同日双腿值；2026-04-03没有同日ECB值。
- 2026-05-04、05-05、06-19存在ECB参考值，但不是该中国交易日历中的开市日。

这些是日期集合比较，未运行模型回放，也未实施前值填补。即使119个同日数值存在，当前历史文件仍不能证明对应历史PUBLIC可用性。新取得的原件也不能用于过去的2026-09-11 SYSTEM目标日。P2可保留缺口；不为通过回放改名、移目标日或倒填时钟。

## 下一实际边界

正式 `source-certification-package-v0002` 需精确manifest_hash和definition_bindings，配合六项带原件引用的 `source-certification-review-v0001` 审查。当前材料不含伪造accepted决定，也不引用合成认证包冒充真实包。待完整Worker软件验收保存后，将此材料与真实候选的其他必需来源一同绑定，再执行实际候选、历史回放与当前运行；显式激活及系统切换独立处理。

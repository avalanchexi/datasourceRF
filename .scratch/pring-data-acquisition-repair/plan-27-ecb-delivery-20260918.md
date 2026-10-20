# ECB 参考交叉汇率接入

依据已确认 decision-27-ecb-reference-cross-20260917.md；无需再次询问口径。继续沿用已同意的公开 seam：获取/AcquisitionRepository/EvidenceRepository、候选 CLI/ModelRepository/投影到 Worker。代码位于 P2 独立工作树，不改主目录现有 WIP。

先使真实归档 ZIP 能通过本地文档导入进入新独立身份，再接通官方 HTTP 获取、原件复核与投影/Worker。导入以实际读取和校验时刻进入 SYSTEM，记录为 document_import，不把归档文件冒充新 HTTP 请求。完整历史 ZIP 没有逐行真实发布日期证明，不能根据 Date 或约16:00日程制造 PUBLIC 时间。

每个值保留同一原件同日 CNY/EUR、USD/EUR 字段和原始数字文本；冻结公式 CNY_per_EUR / USD_per_EUR 及34位十进制计算规则。原始 ZIP、CSV 成员哈希、双腿数值、公式版本和采集回执一起构成可复核血缘。采用项目已有来源计算契约模式，不为两条原始字段虚构其他目录指标，也不声称 ECB 直接发布该交叉报价。

输入须限制 ZIP/解压大小、唯一已知 CSV 成员、列身份、日期唯一性与请求范围；缺腿保留缺口，非数、非正值及格式错误不产生数值。完整响应重新解析对照规范化数据、公式和两腿；旧 FXCM/TMA 声明、手填结果或伪造 PUBLIC 不得进入新身份。修订追加保存，重复采集相同两腿不应把首次可用时刻推后。

已下载真实原件 SHA256 56a389450a063c0637462db6e33575b45048e181a8071adc9cef2438c97c9e51；CSV SHA256 9ee21621a088d3ad15247846e98d27bf4ac19c863e165f6817eff0e6e87770ae。5496个双腿有效日；实际原始请求 URL 及取得时刻在 evidence-27-cnh-alternatives-20260917/ecb-history-receipt.json。本轮先复用原件，不再次下载。

软件契约、合成候选验证与真实来源认证分别记账。实际认证、候选、120中国交易日回放及显式激活/切换仍是后续门；不能因来源或页面可下载就标为已认证。

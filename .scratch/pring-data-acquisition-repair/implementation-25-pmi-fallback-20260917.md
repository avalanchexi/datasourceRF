# #25 PMI 三指标回退与来源传递

实现工作树 `/mnt/d/cursor/datasourceRF-fallback-20260917`；固定比较点 `955a2160a2b558edd819bfd43690f1c797f1641a`，提交 `e19834e280175afe6ce1c8b52d1eabc4a1faea12`。8 个代码及测试文件，394 行新增、58 行删除。未合并、推送或正式激活。

## 行为

新不可变定义可显式声明 `tushare:cn_pmi:official-sampled-v0001`，限定活动、库存、价格三个既有 PMI 指标和 cn_pmi 的八个字段。原件按 API、字段、月份范围、receipt、整份规范化结果复算，仍须通过注册契约；未经独立证明的 PUBLIC 时间拒收，SYSTEM 使用真实取得且校验时刻。该标识不授予来源认证。

TuShare 已交付某指标本期时，官方只补同月缺失的其他指标；既有 TuShare 值与来源声明 ID 保留。所有指标缺失且官方失败时保留缺口，正文实际 acquisition 对应物理请求为 failed/transient_transport_error，证据侧 source_failed/OSError。活动证据现通过 overheat.evidence 到报告 activity_context，库存及价格继续各自既有路径。

## 验证

- 契约、活动投影和报告边界均先有实际红例，见 verification-25-pmi-contract-red、pmi-projection-red、pmi-report-red-20260917.txt。
- 10 个混合交付/官方失败阶段用例，另有原件破坏、伪造 PUBLIC、仅选择库存但同份响应其他活动字段被篡改三个完整性反例。八字段使用不同合成值验证映射，官方值来自已归档真实公告。
- 初次阶段与报告验证 25 passed in 31.20s；完整性阶段 13 passed in 34.13s。增加实际正文物理请求分类断言后的新安装包相关验证：**151 passed in 72.96s，exit=0**，会话 84577 终态结束。
- 源码与独立安装 99 个 py/css/js 文件、10 个测试文件在验证前后指纹全部相同。最终回执 verification-25-pmi-installed-final-20260917.json；日志 SHA256 b88948679e651fcd8f2a93fb7cf6783698468c5fa125d810ce510a2abde3a83f。
- Ruff、六个源文件 mypy、git diff --check 通过。

## Standards 复审

独立 fallback_standards_review 最终未发现新增硬问题。所建议的三个负例、八字段不同值均已补齐。同份 PMI receipt 重复复算是非阻断效率建议，本切片不扩大重构。审查只读，未代替测试执行。

## Spec 复审

独立 fallback_spec_review 最终未发现新增硬问题。混合交付、保留值及来源、报告来源传递与失败分类意见已解决。完整 PMI Worker 的最终完成状态、必需阻断/可选降级仍待统一验收。

## 剩余范围

八项重叠中 CPI、PPI、PMI 三项的软件交付契约与阶段回退已验证；M1/M2、SF 总量、GDP 三项待实现。新输入完整 Worker、真实 PUBLIC 绑定与来源认证、真实候选 120 中国交易日回放、显式激活和系统切换仍开放。旧 PPI 完整 Worker 通过不能代替当前新代码的完整运行验证。272 个归档输入与主目录 WIP 保留；C 盘 14GB、原生盘 832GB 可用，未清理。

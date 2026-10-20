# #25 CPI双通道及按指标官方摄取

实现工作树 `/mnt/d/cursor/datasourceRF-fallback-20260917`，分支 `codex/official-period-fallback`。本切片固定比较点45715b6021ae0e31a7af25438497de43e7a90382；已提交 `955a2160a2b558edd819bfd43690f1c797f1641a`。沿用既有领域规则，不覆盖旧目录或正式激活。

## 行为

- 新不可变目录可显式声明 `tushare:cn_cpi:official-sampled-v0001`，只开放headline的cn_cpi三字段及既有统计含义，核心CPI仍仅官方。该标识自身不授予认证。
- TuShare CPI原件按API、字段、统计月范围、receipt和规范化结果复算后仍须通过注册契约；未独立绑定发布时间时只支持SYSTEM，无证明的PUBLIC时间拒收。
- Worker传递已有RetrievalScope.metric_ids。公告的原件和完整规范化结果保持整页，只有来源声明、成功结果及失败记录限定到所请求指标。未知修订时间仍按整份公告判断。
- 已有TuShare总体CPI而核心CPI缺期时，只补官方核心CPI；原headline声明ID、值9.0、TuShare来源不变。此处刻意用不同的合成值检验只处理新鲜度，不处理数值对账。
- 官方不可用时保留缺口，不制造空观测。实际正文acquisition与物理请求关联后验证failed/transient_transport_error；证据侧为source_failed/OSError。完整Worker必需阻断/可选降级仍待后续验收。

## 红绿证据

1. verification-25-cpi-contract-red-valid-20260917.txt：CPI新交付契约原先拒收。早一份cpi-contract-red因测试tuple.append错误失败，只是夹具修正记录。
2. verification-25-cpi-scope-red-20260917.txt：加入契约后，补核心CPI却新增3个headline官方声明。scope-green为初次修复1通过。
3. verification-25-cpi-ppi-phase-final-20260917.txt：6CPI+6PPI阶段12通过。其前一轮2个空TuShare场景因夹具未捕获既有observations_missing失败；修正夹具而未改变空响应生产语义。
4. verification-25-cpi-lpr-regression-red-20260917.txt：共享摄取入口新增family检查误伤LPR，既有公开摄取用例KeyError。修为默认从解析结果派生范围，显式范围才核对官方family。
5. verification-25-cpi-revision-red-20260917.txt：相同修订页先摄取core、后摄取headline，会恢复未经证明的旧PUBLIC时间。修为整页检查previous/same_document_previous/revision，仅声明筛范围。
6. verification-25-cpi-review-final-20260917.txt：上述修复后，官方适配器、LPR、CPI/PPI阶段合计66通过54.91s。review-fixes上一轮2失败只是新分类断言误用RunRecord未暴露字段，改用公开RetrievalLedger实际acquisition关联，未改生产逻辑。
7. Ruff、mypy五个源文件、当前增量git diff --check均通过。新离线安装99个py/css/js文件逐字节匹配，见verification-25-cpi-install-20260917.json；安装包相关验证正在运行，终态另补。

## Standards复审

遵循code-review技能、fallback_standards_review只读独立审查。最初两项硬问题是LPR共用入口和按scope缩小修订检查；两项都以行为反例复现后修复。最终复审未发现剩余硬问题或额外气味建议；未代替执行回归。

## Spec复审

fallback_spec_review初审未发现实现硬问题，但指出失败分类证明不足；已通过实际article acquisition绑定物理请求补齐阶段分类。最终限定复审未发现新增硬问题。当前切片不声称覆盖完整CPI Worker、剩余六项、真实认证。

## 剩余范围

八项重叠中的CPI、PPI软件交付契约已实现；PMI三项、M1/M2、SF总量、GDP六项仍待实现/验证。可靠PUBLIC原件绑定、真实来源认证、新不可变目录完整准入、120日真实回放和正式激活/切换均未完成。272个归档输入及主目录WIP保留，未做资源清理。合成评审材料和隔离测试不能作为真实认证证据。

## 2026-09-17 22:39 最终验证与保存

独立安装包相关验证 **123 passed in 47.72s，exit=0**，会话4599已结束。源码/安装99个文件以及8个测试文件的终态指纹全部未变；回执 verification-25-cpi-installed-final-20260917.json，日志 verification-25-cpi-installed-related-20260917.txt。两个审查轴均复审通过当前切片；8个代码/测试文件提交 `955a2160a2b558edd819bfd43690f1c797f1641a`，工作树跟踪文件干净。未合并/推送/正式激活，272个未跟踪材料保留。使用Python3.10运行终态记账脚本时不支持datetime.UTC，改用既有Python3.12环境后完成；此工具环境错误未改动代码或测试输入。

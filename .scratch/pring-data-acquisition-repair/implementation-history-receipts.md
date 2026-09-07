Execution: completed-code-batch

# 历史来源 smoke 的真实收据补齐

基点 `a569fd757c7d19a4ae95b980bd2b1c0c51cba973`，沿用已接受票03/13公开采集边界。
[源码研究](source-history-receipt-boundary.md)区分已修的history导入与遗漏的smoke发现/下载；
不是重开全部03，也不更改历史PUBLIC、覆盖日历或来源认证规则。

目录发现和正文下载现在复用AcquisitionRepository：请求前登记、真实收到后保存字节、
校验完成后才validated；HTTPError留错误体，无响应不补received。
线程池每个任务独立复制上下文，保留own_acquisitions所属run；兄弟任务失败时，
已启动的成功/失败获取分别完成自己的收据。一个物理正文共享多family校验，不虚增请求。
目录和正文参数均保留target_business_date，独立调用仍可追溯分析目标。

目录与LPR使用既有禁止重定向transport，原始302保留为失败而非自动另发请求。
正常/错误HTTP体均按路径上限+1读：目录1000001、正文4000001；限额随参数保存，
超限保留有界前缀并拒绝，不能声称该前缀是完整页面。
AcquisitionRepository.capture新增可选max_error_body_bytes，其他调用默认行为未改。

浏览器capture导入先保存原文件字节，再解析包装JSON和HTML；非法包装/HTML也有原输入。
成功normalized.artifact_hash关联解码后的HTML制品，receipt.raw_hash关联原包装；
transport明确browser_capture_import，不冒充当年HTTP接收。后续refresh仍是新document_import。

## 反例与验证

- 首目录HTTP503：1RED/1.81秒，0回执而期望1；初次GREEN1/2.04秒。
- 线程下载：更正RED1失败1通过/2.95秒，22请求仅14目录回执；修复后2通过/3.58秒。
  初稿transport把NBS文档误认目录，触发无效期次（1失败1通过/2.72秒），保留日志但不当作产品缺陷证据。
- 超限目录：1失败5通过/5.48秒，错误继续下一请求；现在有界前缀保留并拒绝。
- Spec初审4项：重定向、原浏览器包装、目标日、错误体上限。首轮5失败9通过/9.03秒；
  浏览器初稿选的Q4不在首8调度，改到最早GDP2023-Q4后独立2RED/3.63秒，
  分别为已读包装无received和raw被替换为HTML。两个草稿错误均保留，不冒充有效RED。
- 修复后14新测试通过9.81秒，追加真实GDP成功包装转换；最终关联70通过51.62秒。
  最后测试替身为urllib响应显式声明msg类型，未改变应用行为；全套覆盖该最终写法。

新增默认测试15项。实际fixture为社融2025-01原件25006字节和GDP2023-Q4原件322515字节，
均从旧CAS精确复制，非新网络请求。[根校验](verification-history-receipts/research-verification.json)
核对两原件及研究报告25链接、16个固定Git输入。真实新来源获取和来源认证次数均0。

Ruff、mypy82、三文件格式检查通过；mypy初查新代码Any返回与测试msg属性缺少声明均已修。
81安装Python文件与工作区一致。Spec原4项复审0；Standards最终复审0。本批一次全套756通过、0失败、938.86秒，退出0；完成后81安装Python文件再次核对一致。[最终记录](verification-history-receipts/final.json)。

[票19下一实施边界](ticket19-implementation-boundary.md)已完成25链接、13固定Git输入根复核。
现有新候选入口缺正式包内容寻址/引用/定义绑定验证能力，可以先实现明确拒绝及synthetic正例；
保留v3隔离，不把A18准备包或certified标签当正式认证，也不提前完成整票或真实创建候选。

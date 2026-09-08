# 核心与仓单标准化制品消费核验

2026-09-09；本批固定基点 `3e1b7d3f4f2421fa72ee2e30ffbaefb11da03f8d`。依据规格第21/34/38项、票02原件与标准化结果可追溯要求及票19新目录消费。沿用已确认的采集、来源声明、PUBLIC/SYSTEM选值和回放公开测试入口，只替换外部transport、时钟及隔离CAS损坏现场。

## 已确认并修复的反例

- 核心PUBLIC回放忽略损坏normalized：[RED](verification-normalized-core-red-01.txt)失败；加入两制品读取后[GREEN](verification-normalized-core-green-01.txt)通过。
- 核心原件正确、normalized为哈希正确的空列表仍能追加来源声明：[RED](verification-normalized-semantics-red-01.txt)失败；重解析全部价格字段并核标准化哈希后，与未来版本/多次取得等[18项回归](verification-normalized-core-green-02.txt)通过。
- 核心入库时normalized已丢失仍能追加声明：[RED](verification-normalized-ingress-red-01.txt)失败；实际入库同时读取两制品后[7项回归](verification-normalized-ingress-green-01.txt)通过。
- 仓单同一声明新增一个原件正确而normalized为空的关联，仍能被检索选择为完整：[RED](verification-normalized-warrant-red-01.txt)失败；全部返回成员、期次、维度、单位和值重解析对应后[7项回归](verification-normalized-warrant-green-01.txt)通过。
- 仓单标准化PUBLIC时间与来源声明不一致仍能选中：[RED](verification-normalized-warrant-time-red-01.txt)失败；新增所选声明时间匹配后[25项仓单回归](verification-normalized-warrant-green-02.txt)通过。
- 显式携带合法目录版本的正常仓单被新校验误拒绝：[RED](verification-normalized-warrant-definition-red-01.txt)失败；调用方传入固定目录版本后[正例通过](verification-normalized-warrant-definition-green-01.txt)。
- 数值修订后的PUBLIC保守降级被新校验误当制品不完整：[SYSTEM上下文RED](verification-normalized-warrant-revision-red-02.txt)失败；保持未知时间与SYSTEM取值两个边界后[10项回归](verification-normalized-warrant-revision-green-01.txt)通过。`revision-red-01`只是对历史target选新值的错误测试预期；历史target保持PUBLIC约束选旧值，不作为代码缺陷证明。

## 实现边界

共享批量读取一次取得的raw和normalized，保留精确声明关联；任一关联制品不可读或损坏时，整条声明不能冒充完整。既有读取原件接口保留，新增完整获取制品接口给仓单消费者使用。核心重解析结果须与receipt标准化哈希一致；仓单解析全部返回成员及标准化声明字段，已知时间断言与所选声明逐项对应。入库政策将两个公开时间保守降为未知时，保留原断言而不授予其PUBLIC资格；SYSTEM仍可核验新值。当前批未创建新官方时间认证。

较晚PUBLIC版本的坏制品不能使更早已知版本失效；多个真实获取关联中有一个坏关联不能以另一份好原件掩盖。测试使用合成来源合同和隔离数据，不代表真实官方样本、实际完整候选或120中国交易日验收。

## 最终软件验收与整体前置

本切片mypy91、Ruff/格式8文件与90安装Python源逐项匹配，[两轴复审](verification-normalized/review.md)剩余0，新增21个用例。第一次[项目默认全套](verification-normalized-full-01.txt)结果为**1022通过、6失败、1错误，2028.77秒**，异常涉及文件句柄耗尽及SQLite无法打开数据库；此失败日志原样保留。随后经公开查询RED与GC对照确认连接释放根因，并完成[连接生命周期修复](implementation-database-connections.md)，新增2个公开资源循环用例。

合并两切片后的[默认全套](verification-connection-full-01.txt)最终为**1031通过、0失败、2975.70秒**，主会话37371退出码0；257关联通过、mypy92及Ruff/格式22文件通过，90安装Python源前后匹配，22冻结输入字节未变。最终证据由[联合检查点](verification-connection/checkpoint.json)绑定。第一次指纹输出被PowerShell输出截断管道中断，残留文件单独保留；完整指纹才用于验收，不把截断输出或原失败运行改写为通过。

LPR、常规官方宏观和银行间消费者的完整normalized边界仍须各自通过公开反例核验；RRR既有重解析和多收据行为也须独立验收，不能用核心/仓单通过代替。融资注册合同、新目录active Worker完整纵向、真实来源认证、业务规则、真实模型可用检索、AI报告网络、120日重放和真实切换均继续开放。

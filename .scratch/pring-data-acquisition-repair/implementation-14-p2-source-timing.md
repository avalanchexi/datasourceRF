Execution: completed-code-batch

# 14续：来源已见期次和发布计划进入读取投影

基点 `ad86bd08f073f000e395f08bb773a22220c01c4e`。[票14](issues/14-p2-availability.md)要求获取结果、认证、真实期次及发布状态可区分；[本批边界](p2-source-timing-boundary.md)定位已存获取元数据没有传到P2投影。

## 行为

投影从同一条、已按目标日/定义/查询时刻筛选的获取记录传递5个已有字段：Treasury的`latest_source_period`、`source_timezone`；EIA的`release_date`、`next_release_date`、`release_timezone`。没有字段就保持null，没有该目标的记录就保持`latest_acquisition=null`。不从其他获取记录补值。

P2页面分别显示“来源已见最新期”“当前批次发布日”“下次计划发布日”和来源时区。来源最新期不是历史目标期必须采用的值；批次日期不是每条历史值首发；计划不是已经发布。PUBLIC未知候选仍被目标模型视图排除，未认证值仍为空，现有统计期/鲜度规则/阶段计算不改变。

新公开集成测试复用真实Treasury/EIA原件，仅替换外部transport，用现有`own_acquisitions`将隔离fixture任务与获取相连。验证取到字段、取得前不可见、另一目标日不可见；页面既有契约测试增加具体标签断言。测试中的builtin模型激活仅存在隔离fixture库，未激活生产模型或授予新来源认证。

## 验证

- [真实缺字段RED](verification-14-p2-source-timing-owned-red.txt)：2失败、18.60秒。之前三次测试设置错误及其修正已在边界文档分别记录，不能算产品缺陷。
- 新代码重新安装到规定WSL非editable环境、等待uv退出0后，[针对结果](verification-14-p2-source-timing-green.txt)：69通过，46.19秒。
- Ruff通过；mypy82文件通过；4个变更文件format check通过。
- [双轴静态审查](verification-14-p2-source-timing/review.md)：Spec0、Standards0。
- 本批全套 **682通过、0失败、742.99秒**，一次运行且退出码0；[完整日志](verification-14-p2-source-timing-pytest-20260907-a.txt)、[最终收据](verification-14-p2-source-timing/final.json)。81个安装Python文件与工作区逐一匹配，审查及测试期间应用源码未再变化。验证于2026-09-08完成。

本批未发起真实HTTP/Tavily/Exa请求，没有生产写入、认证或模型切换。来源日历鲜度规则、P2正式认证和全项目前置仍分别开放，不能只因元数据可读就将13项P2全部称可用。

同期[P1常规官方来源准备](p1-official-preparation.md)及8文件包已完成，根代理分别运行默认Windows标准库制品校验和规定WSL公开纯解析器只读重跑（4.8281秒），均退出0。250份原件20,069,217字节、11家族268调用、18指标1858标量；18代表性独立期望和5专项通过，其余1840标量未逐格事实审计。根重跑另增加268调用，连同子代理记录的804次实际调用为1072，但唯一样本/最终矩阵仍按250/268计，不能放大覆盖率。原件时间字符串与解析器相符仅为该页面时间核验，不是授予历史PUBLIC认证。报告SHA `1a1c6984c96df6da41c76a008c4f37419ef9b23621f6391e84e78e68c3444b5f`；12本地链接与8精确文件均通过。

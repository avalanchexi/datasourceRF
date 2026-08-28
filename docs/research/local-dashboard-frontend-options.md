# Pring 周期驾驶舱本地前端方案调研

> 研究日期：2026-08-21  
> 范围：个人使用、WSL2 localhost、FastAPI后端、只读投影、长任务由独立Worker执行；不评估公网部署和Codex Sites。  
> 证据边界：只使用各项目官方文档，不用二手框架排行榜；“流行”按当前仍活跃、文档成熟且常见于Python数据/Web应用的候选理解，不声称精确市场份额。

## 1. 结论

用户已选择Plotly Dash作为V1本地页面层。Dash 4.2原生支持FastAPI后端和已有FastAPI服务器，因此不需要Flask/WSGI桥接或第二个Web服务。原型和视觉设计按用户决定延后到当前Wayfinder全部完成后另行开展；本研究只冻结架构接缝，不把原型加入当前地图。

```text
FastAPI + Dash 4.2（同一ASGI进程和端口）
  + Dash Pages（页面路由）
  + Plotly Graph Objects（金融与宏观交互图表）
  + dcc.Interval（自适应低频轮询）
  + dash.testing（回调与浏览器验收）
```

静态依赖锁定版本并随应用本地提供，不依赖运行时CDN；V1不引入Node构建链、WebSocket、Redis或Dash后台回调。视觉设计仍由后续Open Design工作完成。

选择这套组合的原因：

1. Dash 4.2可直接使用FastAPI后端，让版本化REST与页面复用同一ASGI应用。[Server Backends](https://dash.plotly.com/server-backends)
2. Plotly原生支持缩放、悬停、筛选和图表联动，适合120日趋势、阶段时间线、收益率曲线和通胀传导。
3. Dash Pages提供稳定的多页URL，`dcc.Interval`足以处理本项目盘后、单用户、长任务状态更新。[Dash Pages](https://dash.plotly.com/urls) [`dcc.Interval`](https://dash.plotly.com/dash-core-components/interval)
4. `dash.testing`提供回调和浏览器测试接缝，页面可以使用固定证据快照验收。[Dash Testing](https://dash.plotly.com/testing)
5. 浏览器只读取只读投影或提交短任务命令；证据、阶段与任务真值仍在领域模块和SQLite，不进入Dash组件状态。

## 2. 候选比较

| 方案 | 轻量与部署 | 展示能力 | 与既有架构匹配 | 主要代价 | 结论 |
| --- | --- | --- | --- | --- | --- |
| FastAPI + Jinja2 + htmx + Bootstrap + ECharts | 单Python服务；前端库可本地静态托管；无Node构建 | 布局和图表自由度高，支持暗色和金融时序图 | 直接复用FastAPI、REST、只读投影和任务账本 | 图表联动和交互要自行组合JS；与用户选择不一致 | 已否决，保留为历史候选 |
| NiceGUI + ECharts | Python开发体验轻，底层已含FastAPI、Vue、Quasar、Tailwind | 默认效果好，表格、ECharts、Highcharts组件丰富 | 可挂在现有FastAPI，适合快速做个人仪表盘 | 所有实时UI通信使用Socket.IO，页面对象和服务器事件循环耦合更强；后续完全定制更受框架约束 | **次选** |
| Streamlit | 最快把Python脚本变为多页数据应用 | 内置数据组件和主题，上手最快 | 更适合探索型分析，不适合把版本化REST、任务命令和不可变快照作为稳定应用边界 | 交互默认触发脚本重跑；多页Widget/Session State有额外语义，复杂应用需要缓存和状态规约 | 不选作V1主界面 |
| Plotly Dash 4.2 | Python图表和回调生态成熟，支持多页；当前可直接使用FastAPI后端 | Plotly交互图、缩放、筛选和联动强 | 可与现有FastAPI同进程；回调只读投影或追加短任务命令 | 必须禁止用Dash后台回调建立第二套任务系统；页面回调测试量高于服务端模板 | **V1已选页面层；视觉设计延后** |

## 3. 关键事实

### 3.1 NiceGUI

NiceGUI官方说明其底层为FastAPI，页面使用Vue、Quasar和Tailwind，内置table、AG Grid、Highcharts和ECharts，并能挂到自有FastAPI应用；这让它非常适合快速原型。[NiceGUI文档](https://nicegui.io/documentation/) [技术基础](https://nicegui.io/documentation/section_foundations)

但官方同时说明所有实时通信使用Socket.IO，UI更新必须遵守其事件循环和页面生命周期。对于本项目这种“持久任务先运行、页面只读取快照”的结构，这会增加一个不必要的状态层。因此把NiceGUI保留为原型备选，不作为V1冻结方案。

### 3.2 Streamlit

Streamlit官方提供成熟的多页导航、缓存、Session State和测试能力，因此很适合快速分析应用。[多页应用](https://docs.streamlit.io/develop/concepts/multipage-apps)

它的核心执行模型仍是用户交互后从上到下重跑脚本；Fragments虽可缩小重跑范围，但仍有容器、缓存和Widget状态限制。[执行与Fragments](https://docs.streamlit.io/develop/concepts/architecture/fragments) 这与本项目要求的稳定URL、HTML/JSON契约、任务账本和历史快照重放并不自然一致。

### 3.3 Dash

Dash官方支持多页、交互图和回调，适合分析仪表盘。[Dash文档](https://dash.plotly.com/) Dash 4.2新增原生FastAPI后端，既可用`backend="fastapi"`创建服务，也可把Dash交给已有FastAPI服务器；这使版本化REST API和Dash页面可以共用同一ASGI应用。[Server Backends](https://dash.plotly.com/server-backends)

Dash Pages提供单页应用式的多页URL导航；`dcc.Interval`可以低频轮询任务状态；`dash.testing`提供回调单元测试和浏览器端到端测试。[Dash Pages](https://dash.plotly.com/urls) [`dcc.Interval`](https://dash.plotly.com/dash-core-components/interval) [Dash Testing](https://dash.plotly.com/testing)

长任务的Dash官方后台回调仍使用本地DiskCache或Celery/Redis。[后台回调](https://dash.plotly.com/background-callbacks) 本项目已经拥有SQLite持久任务账本和独立Worker，因此V1明确禁止Dash后台回调：页面回调只能读取版本化投影、提交短任务命令和低频轮询状态。

### 3.4 后续Dash原型建议（不属于当前Wayfinder）

```text
Dash 4.2 + FastAPI backend
  ├─ Dash Pages：多页导航
  ├─ Plotly Graph Objects：120日趋势、阶段时间线、收益率曲线、宏观联动
  ├─ dcc.Interval：低频任务状态轮询
  ├─ 本地静态CSS/字体：断网可用
  └─ dash.testing：回调与浏览器验收
```

后续原型不得调用TuShare、Tavily、Exa或AI CLI；使用固定的小型证据快照。建议标准至少包括：同一FastAPI端口、无Node/Redis/Celery、三张联动金融图、任务状态通知不启动长回调、空阶段和陈旧/冲突状态可读、断网可运行、核心回调可自动测试。具体页面与视觉验收由Wayfinder结束后的独立设计工作决定。

## 4. V1边界

- Dash回调只能消费应用层返回的只读投影，或以幂等键追加短任务命令；不能直接查询来源表或拼装阶段逻辑。
- 页面使用`dcc.Interval`轮询：活动任务默认30秒，无活动任务默认5分钟或暂停；V1不需要WebSocket、Redis或通知Outbox。
- Plotly只负责展示，图表数据来自版本化只读投影；浏览器不重新计算趋势或正式阶段。
- Dash、Plotly、CSS、字体和图标必须固定版本并本地托管，断网时历史驾驶舱仍能打开。
- 任何AI生成Markdown都按安全Markdown渲染，禁止原始HTML、脚本和未经验证的URL。
- Dash后台回调、DiskCache和Celery不得成为第二套任务系统；所有长任务进入SQLite持久账本，由独立Worker执行。
- 若后续视觉设计发现Dash无法实现已批准交互，必须通过新ADR重新选择前端，不得在运行时并存两套页面实现。

## 5. 验收建议

后续页面契约与实现至少验证：

1. 断网且外部凭据缺失时，历史页面、阶段映射和本地静态资源仍可使用。
2. Worker运行长报告时，页面可轮询任务状态且FastAPI请求不阻塞。
3. 120日图表、阶段时间线、收益率曲线、库存/通胀卡在亮暗主题下均可读。
4. `stale`、`source_failed`、`conflicted`和`current_stage=null`不能只靠颜色区分。
5. Dash回调测试与REST契约测试读取同一应用投影，不出现两套字段含义。

# 搜索发现渠道契约

Tavily 与 Exa 在 Pring V1 中仅用于发现候选来源。无论搜索结果标题或正文如何表述，它们都
不能直接生成 certified claim、不能清除原指标缺口，也不能进入正式投影。账本只保留候选
HTTPS URL、渠道、分类、延迟和预算，不保存完整响应。

## Tavily

依据 [Tavily Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)
和[认证说明](https://docs.tavily.com/documentation/api-reference/introduction)，适配器向
`POST https://api.tavily.com/search` 发送 Bearer 认证。V1 固定 basic 搜索、最多 5 个结果，
关闭 answer、raw content 和图片，减少信用消耗及非必要数据保留。

## Exa

依据 [Exa Search API](https://exa.ai/docs/reference/search)，适配器向
`POST https://api.exa.ai/search` 发送 `x-api-key`，固定最多 5 个结果，不请求正文内容。

两个适配器都把 401/403、402、429、5xx 与其他 4xx 分别归类为认证失败、额度耗尽、限流、
短暂传输失败和语义失败。仅短暂传输失败可以在同一级额外重试两次。API key、认证头、完整
响应、搜索正文和模型推理均不进入运行状态、日志、数据库或页面。

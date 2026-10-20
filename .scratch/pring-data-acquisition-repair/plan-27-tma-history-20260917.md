# 27：TMA 历史入口与使用说明的有界核验

请求前冻结。既有原件 `evidence-2527-20260917/89133da03e511c7f6458fa5fa1c57f51bf3bc4e9d1312db056378d2c481c106f` 的 Next 数据明确给出站点 `https://benchmark.tma.org.hk/benchmark/marketdata`、当前路径 `/benchmark/marketdata`、相对历史链接 `history/usd-cny-spot-rate`，以及下列使用说明附件。读取脚本中的 JSON 文本，不执行脚本。

独立追加批次最多 2 次 GET，每个 URL 一次、无重试/重定向、20 秒超时、响应上限 2 MB，请求之间至少 2 秒并记录实际起止时间。失败原件与状态保留，遇认证要求或超限即停止，不登录、不绕过限制。

1. `https://benchmark.tma.org.hk/benchmark/history/usd-cny-spot-rate`（按已知基准页解析相对链接）。
2. `https://benchmark-api.tma.org.hk/web/file-manager/download-file/f0e8d815-3eba-4d8f-96be-89ba51623b02`（页面使用说明的直接链接）。

目的为核验真实历史取用与页面所指适用条件。页面已有延迟、非商业查看限制，不能据此假定允许持久化并正式采用。本批不写正式库、不调用批量历史 API、不创建账号或标记来源认证。
